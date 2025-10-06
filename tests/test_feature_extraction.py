from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from backend.utils.feature_extraction import extract_features


def test_extract_features_basic():
    events = []
    timestamp = 0.0
    for key in "abc":
        events.append({"key": key, "event": "keydown", "timestamp": timestamp})
        timestamp += 0.05
        events.append({"key": key, "event": "keyup", "timestamp": timestamp})
        timestamp += 0.02
    result = extract_features(events)
    assert result.vector.shape[0] == len(result.feature_names)
    assert result.vector[0] > 0  # mean dwell
    assert result.vector[6] > 0  # typing speed
