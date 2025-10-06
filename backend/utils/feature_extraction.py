"""Feature extraction utilities for keystroke dynamics."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

import numpy as np


@dataclass
class KeystrokeFeatureVector:
    """Structured representation of the extracted numeric feature vector."""

    vector: np.ndarray

    feature_names: List[str]

    def as_dict(self) -> dict[str, float]:
        return {name: float(value) for name, value in zip(self.feature_names, self.vector)}


def _sort_events(events: Iterable[dict]) -> List[dict]:
    try:
        return sorted(events, key=lambda item: float(item["timestamp"]))
    except Exception as exc:  # pragma: no cover - defensive programming
        raise ValueError("Invalid event payload; timestamp missing or malformed") from exc


def extract_features(events: Iterable[dict]) -> KeystrokeFeatureVector:
    """Convert raw keystroke *events* into a numeric feature representation."""
    ordered = _sort_events(events)
    if not ordered:
        raise ValueError("No keystroke events supplied")

    key_down_times: dict[str, float] = {}
    dwell_times: List[float] = []
    strokes: List[tuple[str, float, float]] = []
    keydown_timestamps: List[float] = []
    event_timestamps: List[float] = []
    backspaces = 0

    for event in ordered:
        key = str(event.get("key"))
        etype = event.get("event")
        timestamp = float(event.get("timestamp"))
        event_timestamps.append(timestamp)

        if etype == "keydown":
            key_down_times[key] = timestamp
            keydown_timestamps.append(timestamp)
            if key.lower() == "backspace":
                backspaces += 1
        elif etype == "keyup":
            start = key_down_times.pop(key, None)
            if start is not None:
                dwell = max(timestamp - start, 0.0)
                dwell_times.append(dwell)
                strokes.append((key, start, timestamp))
        else:  # pragma: no cover - ignore unknown events
            continue

    if not dwell_times:
        raise ValueError("Insufficient data to compute dwell times")

    flight_times: List[float] = []
    for (current_key, _, up_time), (_, next_down, _) in zip(strokes, strokes[1:]):
        flight_times.append(max(next_down - up_time, 0.0))

    total_time = max(event_timestamps) - min(event_timestamps)
    total_time = max(total_time, 1e-6)
    typing_speed = len(keydown_timestamps) / total_time

    pauses: List[float] = []
    if len(keydown_timestamps) > 1:
        pauses = [max(b - a, 0.0) for a, b in zip(keydown_timestamps, keydown_timestamps[1:])]

    dwell_array = np.array(dwell_times, dtype=float)
    flight_array = np.array(flight_times if flight_times else [0.0], dtype=float)
    pause_array = np.array(pauses if pauses else [0.0], dtype=float)

    dwell_mean = dwell_array.mean()
    dwell_std = dwell_array.std(ddof=1) if dwell_array.size > 1 else 0.0
    dwell_median = float(np.median(dwell_array))

    flight_mean = flight_array.mean()
    flight_std = flight_array.std(ddof=1) if flight_array.size > 1 else 0.0

    pause_mean = pause_array.mean()
    pause_std = pause_array.std(ddof=1) if pause_array.size > 1 else 0.0
    pause_max = pause_array.max()

    dwell_var = float(np.var(dwell_array, ddof=1)) if dwell_array.size > 1 else 0.0

    # Entropy of dwell time distribution (bin into 5 buckets)
    hist, _ = np.histogram(dwell_array, bins=5, density=True)
    hist = hist[hist > 0]
    entropy = float(-np.sum(hist * np.log2(hist))) if hist.size else 0.0

    feature_names = [
        "dwell_mean",
        "dwell_std",
        "dwell_median",
        "dwell_var",
        "flight_mean",
        "flight_std",
        "typing_speed",
        "pause_mean",
        "pause_std",
        "pause_max",
        "backspace_rate",
        "entropy",
        "flight_median",
        "pause_median",
    ]

    flight_median = float(np.median(flight_array))
    pause_median = float(np.median(pause_array))

    backspace_rate = backspaces / max(len(keydown_timestamps), 1)

    vector = np.array(
        [
            dwell_mean,
            dwell_std,
            dwell_median,
            dwell_var,
            flight_mean,
            flight_std,
            typing_speed,
            pause_mean,
            pause_std,
            pause_max,
            backspace_rate,
            entropy,
            flight_median,
            pause_median,
        ],
        dtype=float,
    )

    # Replace any NaNs (can occur with single-sample std) with zeros for stability.
    vector = np.nan_to_num(vector, nan=0.0, posinf=0.0, neginf=0.0)

    return KeystrokeFeatureVector(vector=vector, feature_names=feature_names)
