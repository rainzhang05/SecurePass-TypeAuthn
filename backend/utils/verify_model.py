"""Utilities for verifying authentication attempts."""
from __future__ import annotations

import io
from dataclasses import dataclass
from pathlib import Path

import joblib
import numpy as np

from . import encryption, train_model


@dataclass
class VerificationResult:
    score: float
    threshold: float
    accepted: bool


_MODELS_DIR = Path(__file__).resolve().parent.parent / "models"


def _model_path(user_id: str) -> Path:
    return _MODELS_DIR / user_id / "model.pkl"


def _threshold_path(user_id: str) -> Path:
    return _MODELS_DIR / user_id / "threshold.json"


def load_pipeline(user_id: str):
    """Load the trained pipeline for *user_id*."""
    path = _model_path(user_id)
    if not path.exists():
        raise FileNotFoundError("Model not trained yet")
    data = encryption.load_encrypted_bytes(path)
    return joblib.load(io.BytesIO(data))


def load_threshold(user_id: str) -> dict:
    """Load the threshold metadata for *user_id*."""
    path = _threshold_path(user_id)
    if not path.exists():
        raise FileNotFoundError("Threshold not available for user")
    return encryption.load_encrypted_json(path)


def evaluate_sample(user_id: str, feature_vector: np.ndarray) -> VerificationResult:
    """Evaluate an authentication attempt for *user_id*."""
    pipeline = load_pipeline(user_id)
    threshold_info = load_threshold(user_id)
    score = float(pipeline.decision_function(feature_vector.reshape(1, -1))[0])
    threshold = float(threshold_info["threshold"])
    accepted = score >= threshold
    return VerificationResult(score=score, threshold=threshold, accepted=accepted)
