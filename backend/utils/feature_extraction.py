"""Feature extraction utilities for keystroke dynamics."""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, Iterable, List, Sequence, Tuple

import numpy as np


@dataclass
class FeatureVector:
    """Container for a numeric feature vector and metadata."""

    features: np.ndarray
    names: Sequence[str]

    def as_dict(self) -> Dict[str, float]:
        return {name: float(value) for name, value in zip(self.names, self.features)}


def _pair_events(events: Sequence[Dict]) -> Dict[str, List[Tuple[float, float]]]:
    down_times: Dict[str, List[float]] = {}
    pairs: Dict[str, List[Tuple[float, float]]] = {}
    for event in sorted(events, key=lambda e: e["ts"]):
        key = event.get("key")
        ts = float(event.get("ts", 0.0))
        etype = event.get("event")
        if etype == "keydown":
            down_times.setdefault(key, []).append(ts)
        elif etype == "keyup":
            pending = down_times.get(key)
            if pending:
                start = pending.pop(0)
                pairs.setdefault(key, []).append((start, ts))
    return pairs


def _dwell_times(pairs: Dict[str, List[Tuple[float, float]]]) -> List[float]:
    return [max(0.0, up - down) for values in pairs.values() for down, up in values]


def _flight_times(events: Sequence[Dict]) -> List[float]:
    ordered = sorted(events, key=lambda e: e["ts"])
    keyups = [e for e in ordered if e.get("event") == "keyup"]
    keydowns = [e for e in ordered if e.get("event") == "keydown"]
    flights: List[float] = []
    for i, up_event in enumerate(keyups[:-1]):
        next_down_candidates = [d for d in keydowns if d["ts"] >= up_event["ts"]]
        if next_down_candidates:
            next_down = next_down_candidates[0]
            flights.append(max(0.0, next_down["ts"] - up_event["ts"]))
    return flights


def _basic_stats(values: Sequence[float]) -> Tuple[float, float, float, float]:
    if not values:
        return 0.0, 0.0, 0.0, 0.0
    arr = np.array(values, dtype=float)
    return float(arr.mean()), float(arr.std()), float(arr.min()), float(arr.max())


def extract_features(events: Sequence[Dict], *, minimum_duration_ms: float = 50.0) -> FeatureVector:
    """Extract numeric features from raw key events."""
    if not events:
        raise ValueError("No events supplied")
    ordered = sorted(events, key=lambda e: e["ts"])
    timestamps = [float(e.get("ts", 0.0)) for e in ordered]
    total_time = max(timestamps) - min(timestamps)
    total_time = max(total_time, 1e-3)
    char_events = [e for e in ordered if e.get("event") == "keydown"]
    char_count = max(len(char_events), 1)

    dwell = _dwell_times(_pair_events(ordered))
    flight = _flight_times(ordered)

    dwell_mean, dwell_std, dwell_min, dwell_max = _basic_stats(dwell)
    flight_mean, flight_std, flight_min, flight_max = _basic_stats(flight)

    speed = char_count / (total_time / 1000.0)
    pauses = [gap for gap in np.diff(sorted(timestamps)) if gap > minimum_duration_ms]
    pause_mean, pause_std, pause_min, pause_max = _basic_stats(pauses)

    backspaces = sum(1 for e in ordered if e.get("key") == "Backspace" and e.get("event") == "keydown")
    error_rate = backspaces / max(char_count, 1)

    dwell_var = dwell_std ** 2
    flight_var = flight_std ** 2

    monotonic = 1.0 if max(dwell_std, flight_std) < 1e-3 else 0.0

    features = np.array(
        [
            dwell_mean,
            dwell_std,
            dwell_min,
            dwell_max,
            flight_mean,
            flight_std,
            flight_min,
            flight_max,
            speed,
            pause_mean,
            pause_std,
            pause_min,
            pause_max,
            error_rate,
            dwell_var,
            flight_var,
            monotonic,
        ],
        dtype=float,
    )

    names = [
        "dwell_mean",
        "dwell_std",
        "dwell_min",
        "dwell_max",
        "flight_mean",
        "flight_std",
        "flight_min",
        "flight_max",
        "typing_speed",
        "pause_mean",
        "pause_std",
        "pause_min",
        "pause_max",
        "error_rate",
        "dwell_variance",
        "flight_variance",
        "monotonic_flag",
    ]
    return FeatureVector(features=features, names=names)


__all__ = ["FeatureVector", "extract_features"]

