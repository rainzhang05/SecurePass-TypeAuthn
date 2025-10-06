"""Model training utilities for SecurePass-TypeAuthn."""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import joblib
import numpy as np
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM

from . import encryption

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


@dataclass
class TrainingSummary:
    samples: int
    threshold: float
    mean_score: float
    std_score: float


def _user_data_dir(user_id: str) -> Path:
    return _DATA_DIR / user_id


def _features_path(user_id: str) -> Path:
    return _user_data_dir(user_id) / "features.csv"


def _model_path(user_id: str) -> Path:
    return _MODELS_DIR / user_id / "model.pkl"


def _threshold_path(user_id: str) -> Path:
    return _MODELS_DIR / user_id / "threshold.json"


def load_features(user_id: str) -> Tuple[np.ndarray, List[str]]:
    """Load the feature matrix for *user_id* from encrypted storage."""
    path = _features_path(user_id)
    if not path.exists():
        raise FileNotFoundError(f"No feature data available for user {user_id}")

    text = encryption.load_encrypted_text(path)
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise ValueError("Feature file is empty")
    header, data_rows = rows[0], rows[1:]
    matrix = np.array([[float(cell) for cell in row] for row in data_rows], dtype=float)
    return matrix, header


def append_feature(user_id: str, feature_vector: np.ndarray, feature_names: List[str]) -> None:
    """Append a feature vector to the encrypted CSV store for the user."""
    path = _features_path(user_id)
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        existing_matrix, header = load_features(user_id)
        if header != feature_names:
            raise ValueError("Feature name mismatch; cannot append to dataset")
        combined = np.vstack([existing_matrix, feature_vector])
        rows = combined.tolist()
    else:
        header = feature_names
        rows = [feature_vector.tolist()]

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)
    writer.writerows(rows)
    encryption.save_encrypted_text(path, buffer.getvalue())


def train_user_model(user_id: str) -> TrainingSummary:
    """Train a One-Class SVM model for *user_id* and persist it to disk."""
    features, feature_names = load_features(user_id)
    if features.shape[0] < 3:
        raise ValueError("At least three enrollment samples are required for training")

    pipeline = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("svm", OneClassSVM(kernel="rbf", gamma="auto", nu=0.05)),
        ]
    )
    pipeline.fit(features)

    scores = pipeline.decision_function(features)
    mean_score = float(np.mean(scores))
    std_score = float(np.std(scores))
    threshold = float(mean_score - 2.0 * std_score)

    model_bytes = io.BytesIO()
    joblib.dump(pipeline, model_bytes)
    encryption.save_encrypted_bytes(_model_path(user_id), model_bytes.getvalue())

    encryption.save_encrypted_json(
        _threshold_path(user_id),
        {
            "threshold": threshold,
            "mean_score": mean_score,
            "std_score": std_score,
            "feature_names": feature_names,
        },
    )

    return TrainingSummary(
        samples=features.shape[0],
        threshold=threshold,
        mean_score=mean_score,
        std_score=std_score,
    )
