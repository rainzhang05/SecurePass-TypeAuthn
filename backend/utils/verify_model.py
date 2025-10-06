"""Verification utilities for keystroke authentication."""
from __future__ import annotations

import io
import json
from typing import Dict

import joblib
import numpy as np

from .feature_extraction import FeatureVector
from .storage import load_model_artifact, read_json, get_user_model_dir
from .train_model import MODEL_FILE, THRESHOLD_FILE


class ModelNotTrainedError(RuntimeError):
    """Raised when a user model has not been trained yet."""


class LivenessError(RuntimeError):
    """Raised when the input fails liveness checks."""


def _load_pipeline(user_id: str):
    payload = load_model_artifact(user_id, MODEL_FILE)
    if payload is None:
        raise ModelNotTrainedError(f"No trained model for user {user_id}")
    buffer = io.BytesIO(payload)
    return joblib.load(buffer)


def _load_threshold(user_id: str) -> Dict[str, float]:
    path = get_user_model_dir(user_id) / THRESHOLD_FILE
    meta = read_json(path)
    if not meta:
        raise ModelNotTrainedError(f"No threshold metadata for {user_id}")
    return meta


def verify_sample(user_id: str, feature_vector: FeatureVector) -> Dict[str, float]:
    if feature_vector.as_dict().get("monotonic_flag", 0.0) >= 1.0:
        raise LivenessError("Detected non-human consistent timing profile")

    pipeline = _load_pipeline(user_id)
    meta = _load_threshold(user_id)

    sample = feature_vector.features.reshape(1, -1)
    score = float(pipeline.decision_function(sample)[0])
    threshold = float(meta.get("threshold", -999.0))
    accepted = score >= threshold

    return {
        "score": score,
        "threshold": threshold,
        "accepted": bool(accepted),
        "mean_score": float(meta.get("mean_score", 0.0)),
        "std_score": float(meta.get("std_score", 0.0)),
    }

