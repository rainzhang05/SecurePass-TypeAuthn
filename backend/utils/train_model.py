"""Training utilities for SecurePass-TypeAuthn models."""
from __future__ import annotations

import io
import json
from dataclasses import dataclass
from typing import List

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score
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
    return Pipeline([
        ("scaler", StandardScaler()),
        (
            "model",
            OneClassSVM(kernel="rbf", gamma="auto", nu=0.05),
        ),
    ])


def _calibrate_threshold(scores: np.ndarray) -> float:
    mean = float(scores.mean())
    std = float(scores.std())
    if std == 0:
        return mean - 1e-3
    quantile = float(np.quantile(scores, 0.05))
    return min(quantile, mean - 0.5 * std)


def train_user_model(user_id: str) -> TrainingResult:
    df = load_features(user_id)
    if df.empty:
        raise ValueError("No features available for training")
    pipeline = _build_pipeline()
    X = df.values.astype(float)
    pipeline.fit(X)

    scores = pipeline.decision_function(X)
    threshold = _calibrate_threshold(scores)

    buffer = io.BytesIO()
    joblib.dump(pipeline, buffer)
    save_model_artifact(user_id, MODEL_FILE, buffer.getvalue())

    write_json(
        get_user_model_dir(user_id) / THRESHOLD_FILE,
        {
            "threshold": float(threshold),
            "mean_score": float(scores.mean()),
            "std_score": float(scores.std()),
            "samples": int(len(df)),
        },
    )

    return TrainingResult(
        samples=len(df),
        threshold=float(threshold),
        mean_score=float(scores.mean()),
        std_score=float(scores.std()),
    )


def add_sample_and_maybe_train(user_id: str, feature_vector: List[float], feature_names: List[str], *, min_samples: int = 3) -> TrainingResult | None:
    df = append_features(user_id, feature_vector, feature_names)
    if len(df) >= min_samples:
        return train_user_model(user_id)
    return None

