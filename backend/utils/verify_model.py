"""Verification utilities for keystroke authentication."""
from __future__ import annotations

import io
from datetime import datetime
from typing import Dict, List, Optional

import joblib
import numpy as np

from .feature_extraction import FeatureVector
from .storage import append_confidence_log, load_model_artifact, read_json, get_user_model_dir
from .train_model import MODEL_FILE, SCALER_FILE, THRESHOLD_FILE


class ModelNotTrainedError(RuntimeError):
    """Raised when a user model has not been trained yet."""


class LivenessError(RuntimeError):
    """Raised when the input fails liveness checks."""


def _load_bundle(user_id: str) -> Dict:
    payload = load_model_artifact(user_id, MODEL_FILE)
    if payload is None:
        raise ModelNotTrainedError(f"No trained model for user {user_id}")
    buffer = io.BytesIO(payload)
    return joblib.load(buffer)


def _load_scaler(user_id: str):
    payload = load_model_artifact(user_id, SCALER_FILE)
    if payload is None:
        raise ModelNotTrainedError(f"No scaler artifact for user {user_id}")
    buffer = io.BytesIO(payload)
    return joblib.load(buffer)


def _load_thresholds(user_id: str) -> Dict[str, float]:
    path = get_user_model_dir(user_id) / THRESHOLD_FILE
    meta = read_json(path)
    if not meta:
        raise ModelNotTrainedError(f"No threshold metadata for {user_id}")
    return meta


def _normalize_score(score: float, stats: Dict[str, float]) -> float:
    return float((score - stats.get("mean", 0.0)) / (stats.get("std", 1.0) or 1.0))


def _ensemble_score(svm_score: float, if_score: float, stats: Dict[str, Dict[str, float]]) -> float:
    svm_norm = _normalize_score(svm_score, stats.get("svm", {}))
    if_norm = _normalize_score(if_score, stats.get("iforest", {}))
    return float((svm_norm + if_norm) / 2.0)


def _compute_partial_scores(
    bundle: Dict,
    scaler,
    feature_vector: FeatureVector,
    thresholds: Dict[str, float],
) -> Dict[str, Optional[float]]:
    if not feature_vector.partials:
        return {"early_confidence": None, "scores": []}

    svm = bundle["svm"]
    iforest = bundle["isolation_forest"]
    stats = bundle.get("score_stats", {})
    ensemble_threshold = float(thresholds.get("threshold", 0.0))

    early_confidence: Optional[float] = None
    partial_scores: List[float] = []
    for partial in feature_vector.partials:
        scaled = scaler.transform(partial.reshape(1, -1))
        svm_score = float(svm.decision_function(scaled)[0])
        if_score = float(iforest.score_samples(scaled)[0])
        score = _ensemble_score(svm_score, if_score, stats)
        partial_scores.append(score)
        if early_confidence is None and score >= ensemble_threshold:
            early_confidence = score
            break
    return {"early_confidence": early_confidence, "scores": partial_scores}


def verify_sample(user_id: str, feature_vector: FeatureVector, *, log_confidence: bool = True) -> Dict[str, float]:
    if feature_vector.as_dict().get("monotonic_flag", 0.0) >= 1.0:
        raise LivenessError("Detected non-human consistent timing profile")

    bundle = _load_bundle(user_id)
    scaler = _load_scaler(user_id)
    thresholds = _load_thresholds(user_id)

    svm = bundle["svm"]
    iforest = bundle["isolation_forest"]
    stats = bundle.get("score_stats", {})

    sample = feature_vector.raw.reshape(1, -1)
    scaled = scaler.transform(sample)

    svm_score = float(svm.decision_function(scaled)[0])
    if_score = float(iforest.score_samples(scaled)[0])

    ensemble_threshold = float(thresholds.get("threshold", 0.0))
    svm_threshold = float(thresholds.get("svm_threshold", ensemble_threshold))
    if_threshold = float(thresholds.get("iforest_threshold", ensemble_threshold))

    ensemble_confidence = _ensemble_score(svm_score, if_score, stats)

    svm_accept = svm_score >= svm_threshold
    if_accept = if_score >= if_threshold
    ensemble_accept = ensemble_confidence >= ensemble_threshold

    decision: str
    accepted: bool
    if svm_accept and if_accept:
        decision = "accept"
        accepted = True
    elif not svm_accept and not if_accept:
        decision = "reject"
        accepted = False
    else:
        decision = "need_more"
        accepted = ensemble_accept

    partial_data = _compute_partial_scores(bundle, scaler, feature_vector, thresholds)
    if decision == "need_more" and partial_data["early_confidence"] is not None:
        decision = "accept"
        accepted = True

    result = {
        "svm_score": svm_score,
        "iforest_score": if_score,
        "ensemble_score": ensemble_confidence,
        "score": ensemble_confidence,
        "threshold": ensemble_threshold,
        "svm_threshold": svm_threshold,
        "iforest_threshold": if_threshold,
        "accepted": bool(accepted),
        "decision": decision,
        "confidence_history": partial_data["scores"],
        "early_confidence": partial_data["early_confidence"],
    }

    if log_confidence:
        append_confidence_log(
            user_id,
            {
                "timestamp": datetime.utcnow().isoformat(),
                "score": ensemble_confidence,
                "svm_score": svm_score,
                "iforest_score": if_score,
                "decision": decision,
            },
        )

    return result
