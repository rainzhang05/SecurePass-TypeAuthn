"""Training utilities for SecurePass-TypeAuthn models."""
from __future__ import annotations

import io
import json
from dataclasses import dataclass
from pathlib import Path
from datetime import datetime
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

from .feature_extraction import TIMING_FEATURE_KEYS
from .storage import (
    METADATA_COLUMNS,
    append_features,
    get_user_model_dir,
    load_features,
    read_json,
    save_model_artifact,
    write_json,
)


@dataclass
class TrainingResult:
    samples: int
    threshold: float
    mean_score: float
    std_score: float
    metrics: Dict[str, float]


MODEL_FILE = "model.pkl"
SCALER_FILE = "scaler.pkl"
THRESHOLD_FILE = "threshold.json"
METRICS_FILE = "metrics.json"


def _split_train_validation(X: np.ndarray, *, random_state: int = 42) -> Tuple[np.ndarray, np.ndarray]:
    if len(X) <= 1:
        return X, X
    test_size = max(1, int(np.ceil(0.2 * len(X))))
    train_idx, val_idx = train_test_split(
        np.arange(len(X)), test_size=test_size, shuffle=True, random_state=random_state
    )
    return X[train_idx], X[val_idx]


def _augment_samples(
    X: np.ndarray,
    *,
    timing_indices: Sequence[int],
    min_variants: int = 3,
    max_variants: int = 5,
    noise_range: Tuple[float, float] = (0.05, 0.1),
    random_state: int = 42,
) -> np.ndarray:
    if X.size == 0:
        return X
    rng = np.random.default_rng(random_state)
    augmented: List[np.ndarray] = [X]
    timing_indices = list(timing_indices)
    for row in X:
        variants = rng.integers(min_variants, max_variants + 1)
        for _ in range(int(variants)):
            jitter = row.copy()
            if timing_indices:
                scales = rng.uniform(noise_range[0], noise_range[1], size=len(timing_indices))
                noise = rng.normal(0.0, np.maximum(np.abs(row[timing_indices]), 1e-3) * scales)
                jitter[timing_indices] = row[timing_indices] + noise
            else:
                noise = rng.normal(0.0, np.maximum(np.abs(row), 1e-3) * noise_range[0])
                jitter = row + noise
            augmented.append(jitter)
    return np.vstack(augmented)


def _generate_synthetic_impostors(
    X: np.ndarray,
    *,
    multiplier: int = 4,
    random_state: int = 42,
) -> np.ndarray:
    if X.size == 0:
        return X
    rng = np.random.default_rng(random_state)
    cov = np.cov(X, rowvar=False)
    if np.isscalar(cov):
        cov = np.array([[float(cov) + 1e-3]])
    else:
        cov = np.asarray(cov) + np.eye(X.shape[1]) * 1e-3
    mean = np.mean(X, axis=0)
    size = max(multiplier * len(X), len(X))
    try:
        samples = rng.multivariate_normal(mean, cov, size=size)
    except np.linalg.LinAlgError:
        samples = rng.normal(loc=mean, scale=np.sqrt(np.diag(cov) + 1e-3), size=(size, X.shape[1]))
    return samples


def _normalize_scores(scores: np.ndarray, mean: float, std: float) -> np.ndarray:
    return (scores - mean) / (std + 1e-6)


def _calibrate_threshold(positive: np.ndarray, negative: np.ndarray) -> float:
    if positive.size == 0:
        return float(np.mean(negative))
    candidates = np.unique(np.concatenate([positive, negative]))
    if candidates.size == 0:
        return 0.0
    best_threshold = float(candidates[0])
    best_cost = float("inf")
    for threshold in candidates:
        far = float(np.mean(negative >= threshold))
        frr = float(np.mean(positive < threshold))
        cost = far + frr
        if cost < best_cost:
            best_cost = cost
            best_threshold = float(threshold)
    return best_threshold


def _score_metrics(
    positive: np.ndarray,
    negative: np.ndarray,
    threshold: float,
) -> Dict[str, float]:
    far = float(np.mean(negative >= threshold)) if negative.size else 0.0
    frr = float(np.mean(positive < threshold)) if positive.size else 0.0
    accuracy = 0.0
    total = positive.size + negative.size
    if total:
        tp = float(np.sum(positive >= threshold))
        tn = float(np.sum(negative < threshold))
        accuracy = float((tp + tn) / total)
    auc = 0.0
    if positive.size and negative.size:
        labels = np.concatenate([np.ones_like(positive), np.zeros_like(negative)])
        scores = np.concatenate([positive, negative])
        if len(np.unique(labels)) > 1:
            auc = float(roc_auc_score(labels, scores))
    return {"far": far, "frr": frr, "accuracy": accuracy, "auc": auc}


def train_user_model(user_id: str) -> TrainingResult:
    df = load_features(user_id, include_metadata=True)
    if df.empty:
        raise ValueError("No features available for training")

    feature_cols = [c for c in df.columns if c not in METADATA_COLUMNS]
    feature_df = df[feature_cols]
    X_raw = feature_df.values.astype(float)
    feature_names = list(feature_df.columns)
    timing_indices = [i for i, name in enumerate(feature_names) if name in TIMING_FEATURE_KEYS]

    X_train, X_val = _split_train_validation(X_raw)
    augmented_train = _augment_samples(X_train, timing_indices=timing_indices, random_state=42)

    scaler = StandardScaler()
    scaler.fit(augmented_train)

    param_grid = [(gamma, nu) for gamma in ["scale", 0.1, 0.01] for nu in [0.01, 0.05, 0.1]]
    best_auc = -np.inf
    best_params = ("scale", 0.05)

    X_train_scaled = scaler.transform(augmented_train)
    X_val_scaled = scaler.transform(X_val)
    synthetic_negatives = _generate_synthetic_impostors(X_train_scaled)

    for gamma, nu in param_grid:
        model = OneClassSVM(kernel="rbf", gamma=gamma, nu=nu)
        model.fit(X_train_scaled)
        pos_scores = model.decision_function(X_val_scaled)
        neg_scores = model.decision_function(synthetic_negatives)
        if pos_scores.size == 0:
            continue
        labels = np.concatenate([np.ones_like(pos_scores), np.zeros_like(neg_scores)])
        scores = np.concatenate([pos_scores, neg_scores])
        auc = float(roc_auc_score(labels, scores)) if len(np.unique(labels)) > 1 else -np.inf
        if auc > best_auc:
            best_auc = auc
            best_params = (gamma, nu)

    # Refit scaler/model on the full dataset (with augmentation).
    augmented_full = _augment_samples(X_raw, timing_indices=timing_indices, random_state=123)
    scaler = StandardScaler().fit(augmented_full)
    X_full_scaled = scaler.transform(augmented_full)
    svm = OneClassSVM(kernel="rbf", gamma=best_params[0], nu=best_params[1])
    svm.fit(X_full_scaled)

    X_original_scaled = scaler.transform(X_raw)
    isolation_forest = IsolationForest(
        n_estimators=200,
        contamination=0.05,
        random_state=42,
    )
    isolation_forest.fit(X_original_scaled)

    svm_train_scores = svm.decision_function(X_original_scaled)
    if_train_scores = isolation_forest.score_samples(X_original_scaled)
    svm_stats = {"mean": float(np.mean(svm_train_scores)), "std": float(np.std(svm_train_scores) + 1e-6)}
    if_stats = {"mean": float(np.mean(if_train_scores)), "std": float(np.std(if_train_scores) + 1e-6)}

    X_val_scaled = scaler.transform(X_val)
    synthetic_negatives = _generate_synthetic_impostors(X_original_scaled, multiplier=5)
    svm_val_scores = svm.decision_function(X_val_scaled)
    svm_neg_scores = svm.decision_function(synthetic_negatives)
    if_val_scores = isolation_forest.score_samples(X_val_scaled)
    if_neg_scores = isolation_forest.score_samples(synthetic_negatives)

    svm_threshold = _calibrate_threshold(svm_val_scores, svm_neg_scores)
    if_threshold = _calibrate_threshold(if_val_scores, if_neg_scores)

    svm_val_norm = _normalize_scores(svm_val_scores, svm_stats["mean"], svm_stats["std"])
    svm_neg_norm = _normalize_scores(svm_neg_scores, svm_stats["mean"], svm_stats["std"])
    if_val_norm = _normalize_scores(if_val_scores, if_stats["mean"], if_stats["std"])
    if_neg_norm = _normalize_scores(if_neg_scores, if_stats["mean"], if_stats["std"])

    ensemble_val_scores = 0.5 * (svm_val_norm + if_val_norm)
    ensemble_neg_scores = 0.5 * (svm_neg_norm + if_neg_norm)
    ensemble_threshold = _calibrate_threshold(ensemble_val_scores, ensemble_neg_scores)

    metrics = _score_metrics(ensemble_val_scores, ensemble_neg_scores, ensemble_threshold)
    metrics.update({"samples": int(len(X_raw)), "svm_auc": float(best_auc) if best_auc > -np.inf else 0.0})

    # Persist artifacts.
    bundle = {
        "svm": svm,
        "isolation_forest": isolation_forest,
        "feature_names": feature_names,
        "timing_indices": timing_indices,
        "score_stats": {"svm": svm_stats, "iforest": if_stats},
    }

    buffer = io.BytesIO()
    joblib.dump(bundle, buffer)
    save_model_artifact(user_id, MODEL_FILE, buffer.getvalue())

    buffer = io.BytesIO()
    joblib.dump(scaler, buffer)
    save_model_artifact(user_id, SCALER_FILE, buffer.getvalue())

    threshold_payload = {
        "threshold": float(ensemble_threshold),
        "svm_threshold": float(svm_threshold),
        "iforest_threshold": float(if_threshold),
        "mean_score": float(np.mean(ensemble_val_scores)) if ensemble_val_scores.size else 0.0,
        "std_score": float(np.std(ensemble_val_scores)) if ensemble_val_scores.size else 0.0,
    }
    write_json(get_user_model_dir(user_id) / THRESHOLD_FILE, threshold_payload)
    write_json(get_user_model_dir(user_id) / METRICS_FILE, metrics)

    return TrainingResult(
        samples=len(X_raw),
        threshold=float(ensemble_threshold),
        mean_score=float(threshold_payload["mean_score"]),
        std_score=float(threshold_payload["std_score"]),
        metrics=metrics,
    )


def add_sample_and_maybe_train(
    user_id: str,
    feature_vector: Sequence[float],
    feature_names: Sequence[str],
    *,
    min_samples: int = 5,
    auto_retrain_samples: int = 10,
    session_id: Optional[str] = None,
    timestamp: Optional[datetime] = None,
    checksum: Optional[str] = None,
) -> TrainingResult | None:
    df = append_features(
        user_id,
        feature_vector,
        feature_names,
        session_id=session_id,
        timestamp=timestamp,
        checksum=checksum,
    )
    sample_count = len(df)
    if sample_count < min_samples:
        return None

    metrics_path = get_user_model_dir(user_id) / METRICS_FILE
    meta = read_json(metrics_path)
    last_trained = int(meta.get("samples", 0)) if meta else 0

    if last_trained == 0 and sample_count >= min_samples:
        return train_user_model(user_id)
    if sample_count >= auto_retrain_samples and sample_count > last_trained:
        return train_user_model(user_id)
    return None
