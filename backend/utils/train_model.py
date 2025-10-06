"""Training utilities for SecurePass-TypeAuthn models."""
from __future__ import annotations

import io
import json
from dataclasses import dataclass
from typing import List

import joblib
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

from .storage import append_features, load_features, save_model_artifact, write_json, get_user_model_dir


@dataclass
class TrainingResult:
    samples: int
    threshold: float
    mean_score: float
    std_score: float


THRESHOLD_FILE = "threshold.json.enc"
MODEL_FILE = "model.pkl.enc"


def _build_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("scaler", StandardScaler()),
            ("pca", PCA(n_components=0.95, whiten=True)),
            (
                "model",
                OneClassSVM(kernel="rbf", gamma="scale", nu=0.08),
            ),
        ]
    )


def _generate_synthetic_impostors(X: np.ndarray, *, factor: int = 6) -> np.ndarray:
    mean = np.mean(X, axis=0)
    std = np.std(X, axis=0) + 1e-3
    samples = max(factor * len(X), len(X))
    return np.random.normal(loc=mean, scale=std, size=(samples, X.shape[1]))


def _calibrate_threshold(positive_scores: np.ndarray, negative_scores: np.ndarray) -> float:
    pos_quantile = float(np.quantile(positive_scores, 0.1))
    neg_max = float(np.max(negative_scores))
    neg_quantile = float(np.quantile(negative_scores, 0.9))
    threshold = max(pos_quantile, min(neg_max, neg_quantile))
    return min(threshold, float(np.max(positive_scores)))


def train_user_model(user_id: str) -> TrainingResult:
    df = load_features(user_id)
    if df.empty:
        raise ValueError("No features available for training")
    pipeline = _build_pipeline()
    X = df.values.astype(float)
    pipeline.fit(X)

    scores = pipeline.decision_function(X)
    impostor_samples = _generate_synthetic_impostors(X)
    impostor_scores = pipeline.decision_function(impostor_samples)
    threshold = _calibrate_threshold(scores, impostor_scores)

    buffer = io.BytesIO()
    joblib.dump(pipeline, buffer)
    save_model_artifact(user_id, MODEL_FILE, buffer.getvalue())

    write_json(
        get_user_model_dir(user_id) / THRESHOLD_FILE,
        {
            "threshold": float(threshold),
            "mean_score": float(scores.mean()),
            "std_score": float(scores.std()),
            "impostor_mean": float(impostor_scores.mean()),
            "impostor_std": float(impostor_scores.std()),
            "impostor_max": float(impostor_scores.max()),
            "samples": int(len(df)),
        },
    )

    return TrainingResult(
        samples=len(df),
        threshold=float(threshold),
        mean_score=float(scores.mean()),
        std_score=float(scores.std()),
    )


def add_sample_and_maybe_train(
    user_id: str, feature_vector: List[float], feature_names: List[str], *, min_samples: int = 5
) -> TrainingResult | None:
    df = append_features(user_id, feature_vector, feature_names)
    if len(df) >= min_samples:
        return train_user_model(user_id)
    return None

