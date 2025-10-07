"""Evaluate trained SecurePass-TypeAuthn models and produce metrics."""
from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Dict, List

import joblib
import matplotlib.pyplot as plt
import numpy as np
from sklearn.metrics import auc, roc_curve

from backend.utils.storage import (
    DATA_DIR,
    get_user_model_dir,
    load_features,
    load_model_artifact,
    read_json,
)
from backend.utils.train_model import MODEL_FILE, SCALER_FILE, THRESHOLD_FILE

REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(exist_ok=True)


def _normalize(score: np.ndarray, stats: Dict[str, float]) -> np.ndarray:
    return (score - stats.get("mean", 0.0)) / (stats.get("std", 1.0) or 1.0)


def _generate_impostors(X: np.ndarray, *, multiplier: int = 5) -> np.ndarray:
    if X.size == 0:
        return X
    cov = np.cov(X, rowvar=False)
    if np.isscalar(cov):
        cov = np.array([[float(cov) + 1e-3]])
    else:
        cov = np.asarray(cov) + np.eye(X.shape[1]) * 1e-3
    mean = np.mean(X, axis=0)
    size = max(multiplier * len(X), len(X))
    rng = np.random.default_rng(123)
    try:
        samples = rng.multivariate_normal(mean, cov, size=size)
    except np.linalg.LinAlgError:
        samples = rng.normal(loc=mean, scale=np.sqrt(np.diag(cov) + 1e-3), size=(size, X.shape[1]))
    return samples


def _evaluate_user(user_id: str) -> Dict[str, object]:
    features = load_features(user_id)
    if features.empty:
        return {}

    model_bytes = load_model_artifact(user_id, MODEL_FILE)
    scaler_bytes = load_model_artifact(user_id, SCALER_FILE)
    if model_bytes is None or scaler_bytes is None:
        return {}

    bundle = joblib.load(io.BytesIO(model_bytes))
    scaler = joblib.load(io.BytesIO(scaler_bytes))
    thresholds = read_json(get_user_model_dir(user_id) / THRESHOLD_FILE)
    if not thresholds:
        return {}

    X = features.values.astype(float)
    scaled = scaler.transform(X)

    svm = bundle["svm"]
    iforest = bundle["isolation_forest"]
    stats = bundle.get("score_stats", {})

    svm_scores = svm.decision_function(scaled)
    if_scores = iforest.score_samples(scaled)
    ensemble_scores = 0.5 * (_normalize(svm_scores, stats.get("svm", {})) + _normalize(if_scores, stats.get("iforest", {})))
    threshold = float(thresholds.get("threshold", 0.0))

    impostors = _generate_impostors(scaled)
    svm_impostor = svm.decision_function(impostors)
    if_impostor = iforest.score_samples(impostors)
    ensemble_impostor = 0.5 * (
        _normalize(svm_impostor, stats.get("svm", {})) + _normalize(if_impostor, stats.get("iforest", {}))
    )

    far = float(np.mean(ensemble_impostor >= threshold))
    frr = float(np.mean(ensemble_scores < threshold))
    accuracy = float(
        (
            np.sum(ensemble_scores >= threshold) + np.sum(ensemble_impostor < threshold)
        )
        / (len(ensemble_scores) + len(ensemble_impostor))
    )

    labels = np.concatenate([np.ones_like(ensemble_scores), np.zeros_like(ensemble_impostor)])
    roc_scores = np.concatenate([ensemble_scores, ensemble_impostor])
    fpr, tpr, _ = roc_curve(labels, roc_scores)
    roc_auc = float(auc(fpr, tpr))

    plt.figure(figsize=(6, 4))
    plt.plot(fpr, tpr, label=f"AUC={roc_auc:.3f}")
    plt.plot([0, 1], [0, 1], linestyle="--", color="gray")
    plt.xlabel("False Positive Rate")
    plt.ylabel("True Positive Rate")
    plt.title(f"ROC Curve - {user_id}")
    plt.legend()
    plt.tight_layout()
    plt.savefig(REPORTS_DIR / f"{user_id}_roc.png")
    plt.close()

    feature_importance = {}
    if hasattr(iforest, "feature_importances_"):
        importances = iforest.feature_importances_
        for name, value in sorted(zip(features.columns, importances), key=lambda x: x[1], reverse=True):
            feature_importance[name] = float(value)

    return {
        "user_id": user_id,
        "samples": int(len(features)),
        "threshold": threshold,
        "far": far,
        "frr": frr,
        "accuracy": accuracy,
        "auc": roc_auc,
        "confidence_mean": float(np.mean(ensemble_scores)),
        "confidence_std": float(np.std(ensemble_scores)),
        "feature_importance": feature_importance,
        "roc_curve": f"{user_id}_roc.png",
    }


def main() -> None:
    metrics: List[Dict[str, object]] = []
    for user_dir in DATA_DIR.glob("*"):
        if not user_dir.is_dir():
            continue
        user_id = user_dir.name
        result = _evaluate_user(user_id)
        if result:
            metrics.append(result)

    (REPORTS_DIR / "metrics.json").write_text(json.dumps({"users": metrics}, indent=2))


if __name__ == "__main__":
    main()
