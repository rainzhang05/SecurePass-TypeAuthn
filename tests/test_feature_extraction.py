import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from backend.utils.feature_extraction import extract_features


def test_extract_features_basic():
    events = [
        {"key": "a", "event": "keydown", "ts": 0},
        {"key": "a", "event": "keyup", "ts": 80},
        {"key": "b", "event": "keydown", "ts": 120},
        {"key": "b", "event": "keyup", "ts": 200},
        {"key": "Backspace", "event": "keydown", "ts": 260},
        {"key": "Backspace", "event": "keyup", "ts": 280},
    ]

    feature_vector = extract_features(events)
    assert feature_vector.features.shape[0] == len(feature_vector.names)
    data = feature_vector.as_dict()
    assert data["dwell_mean"] >= 0
    assert data["flight_mean"] >= 0
    assert data["error_rate"] > 0

