"""Evaluate trained SecurePass-TypeAuthn models and produce metrics."""
from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Dict, List

import joblib
import numpy as np

from backend.utils.storage import DATA_DIR, get_user_model_dir, load_features, load_model_artifact, read_json
from backend.utils.train_model import MODEL_FILE, THRESHOLD_FILE


def _load_threshold_meta(user_id: str) -> Dict[str, float]:
    path = get_user_model_dir(user_id) / THRESHOLD_FILE
    if not path.exists():
        return {}
    return read_json(path)


def _evaluate_user(user_id: str) -> Dict[str, float]:
    features = load_features(user_id)
    if features.empty:
        return {}
    pipeline_bytes = load_model_artifact(user_id, MODEL_FILE)
    if pipeline_bytes is None:
        return {}
    pipeline = joblib.load(io.BytesIO(pipeline_bytes))
    meta = _load_threshold_meta(user_id)
    threshold = float(meta.get("threshold", 0.0))

    X = features.values.astype(float)
    scores = pipeline.decision_function(X)
    fr = float(np.mean(scores < threshold))

    impostor = np.random.normal(
        loc=np.mean(X, axis=0),
        scale=np.std(X, axis=0) + 1e-3,
        size=(max(5, len(X)), X.shape[1]),
    )
    impostor_scores = pipeline.decision_function(impostor)
    fa = float(np.mean(impostor_scores >= threshold))

    genuine_accept = float(np.mean(scores >= threshold))
    impostor_reject = float(np.mean(impostor_scores < threshold))
    accuracy = float(
        (genuine_accept * len(scores) + impostor_reject * len(impostor_scores))
        / (len(scores) + len(impostor_scores))
    )

    eer = float((fa + fr) / 2.0)

    return {
        "user_id": user_id,
        "samples": int(len(X)),
        "threshold": threshold,
        "far": fa,
        "frr": fr,
        "accuracy": accuracy,
        "eer": eer,
    }


def main() -> None:
    reports_dir = Path("reports")
    reports_dir.mkdir(exist_ok=True)
    metrics: List[Dict[str, float]] = []

    for user_dir in DATA_DIR.glob("*"):
        if not user_dir.is_dir():
            continue
        user_id = user_dir.name
        result = _evaluate_user(user_id)
        if result:
            metrics.append(result)

    payload = {"users": metrics}
    (reports_dir / "metrics.json").write_text(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()

