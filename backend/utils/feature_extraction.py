"""Feature extraction utilities for keystroke dynamics."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
from sklearn.preprocessing import StandardScaler

TIMING_FEATURE_KEYS = {
    "mean_dwell",
    "std_dwell",
    "min_dwell",
    "max_dwell",
    "mean_flight",
    "std_flight",
    "min_flight",
    "max_flight",
    "avg_word_gap",
    "pause_over_300ms",
    "pause_over_700ms",
    "pause_over_1000ms",
    "typing_speed",
    "correction_latency",
    "burstiness",
    "entropy_dwell",
    "entropy_flight",
    "total_duration_ms",
    "pause_mean",
    "pause_std",
    "pause_min",
    "pause_max",
    "interval_mean",
    "interval_std",
    "interval_min",
    "interval_max",
}


@dataclass
class FeatureVector:
    """Container for a numeric feature vector and metadata."""

    names: Sequence[str]
    raw: np.ndarray
    normalized: Optional[np.ndarray] = None
    partials: Optional[List[np.ndarray]] = None

    @property
    def features(self) -> np.ndarray:
        return self.normalized if self.normalized is not None else self.raw

    def as_dict(self) -> Dict[str, float]:
        return {name: float(value) for name, value in zip(self.names, self.features)}

    def raw_dict(self) -> Dict[str, float]:
        return {name: float(value) for name, value in zip(self.names, self.raw)}


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
    ordered = sorted(events, key=lambda e: float(e["ts"]))
    keyups = [e for e in ordered if e.get("event") == "keyup"]
    keydowns = [e for e in ordered if e.get("event") == "keydown"]
    flights: List[float] = []
    for i, up_event in enumerate(keyups[:-1]):
        up_ts = float(up_event.get("ts", 0.0))
        next_down_candidates = [
            d for d in keydowns if float(d.get("ts", 0.0)) >= up_ts
        ]
        if next_down_candidates:
            next_down = next_down_candidates[0]
            flights.append(max(0.0, float(next_down.get("ts", 0.0)) - up_ts))
    return flights


def _basic_stats(values: Sequence[float]) -> Tuple[float, float, float, float]:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return 0.0, 0.0, 0.0, 0.0
    return float(arr.mean()), float(arr.std()), float(arr.min()), float(arr.max())


def _shannon_entropy(values: Sequence[float]) -> float:
    if not values:
        return 0.0
    arr = np.array([v for v in values if v > 0], dtype=float)
    if arr.size == 0:
        return 0.0
    total = float(arr.sum())
    if total <= 0:
        return 0.0
    probs = arr / total
    return float(-np.sum(probs * np.log2(probs + 1e-12)))


def _word_gap_times(events: Sequence[Dict]) -> List[float]:
    ordered = sorted(events, key=lambda e: e["ts"])
    gaps: List[float] = []
    for idx, event in enumerate(ordered[:-1]):
        if event.get("event") != "keyup":
            continue
        if event.get("key") not in {" ", "Space", "Spacebar"}:
            continue
        next_keydown = next(
            (e for e in ordered[idx + 1 :] if e.get("event") == "keydown"),
            None,
        )
        if next_keydown:
            gap = float(next_keydown.get("ts", 0.0)) - float(event.get("ts", 0.0))
            if gap >= 0:
                gaps.append(gap)
    return gaps


def _pause_threshold_fractions(flights: Sequence[float], *, thresholds: Iterable[float]) -> Dict[float, float]:
    if not flights:
        return {th: 0.0 for th in thresholds}
    total = float(len(flights))
    return {th: float(sum(1 for f in flights if f >= th)) / total for th in thresholds}


def _correction_latency(events: Sequence[Dict]) -> List[float]:
    ordered = sorted(events, key=lambda e: e["ts"])
    latencies: List[float] = []
    for idx, event in enumerate(ordered):
        if event.get("event") != "keydown" or event.get("key") != "Backspace":
            continue
        next_keydown = next(
            (
                e
                for e in ordered[idx + 1 :]
                if e.get("event") == "keydown" and e.get("key") != "Backspace"
            ),
            None,
        )
        if next_keydown:
            latency = float(next_keydown.get("ts", 0.0)) - float(event.get("ts", 0.0))
            if latency >= 0:
                latencies.append(latency)
    return latencies


def _slice_events_by_keystrokes(
    events: Sequence[Dict],
    *,
    keydown_target: int,
) -> List[Dict]:
    subset: List[Dict] = []
    keydown_count = 0
    active = Counter()
    for event in events:
        subset.append(event)
        if event.get("event") == "keydown":
            keydown_count += 1
            key = event.get("key") or ""
            active[key] += 1
        elif event.get("event") == "keyup":
            key = event.get("key") or ""
            if active.get(key, 0) > 0:
                active[key] -= 1
                if active[key] <= 0:
                    active.pop(key, None)
        if keydown_count >= keydown_target and not active:
            break
    return subset


def _compute_feature_map(
    ordered_events: Sequence[Dict], *, minimum_duration_ms: float = 50.0
) -> Dict[str, float]:
    timestamps = [float(e.get("ts", 0.0)) for e in ordered_events]
    if not timestamps:
        raise ValueError("No timestamps present in events")
    total_time = max(timestamps) - min(timestamps)
    total_time = max(total_time, 1e-3)
    keydown_events = [e for e in ordered_events if e.get("event") == "keydown"]
    char_count = max(len(keydown_events), 1)

    dwell = _dwell_times(_pair_events(ordered_events))
    flight = _flight_times(ordered_events)
    intervals = np.diff(sorted(timestamps))
    pauses = [gap for gap in intervals if gap > minimum_duration_ms]

    dwell_mean, dwell_std, dwell_min, dwell_max = _basic_stats(dwell)
    flight_mean, flight_std, flight_min, flight_max = _basic_stats(flight)

    pause_mean, pause_std, pause_min, pause_max = _basic_stats(pauses)
    pause_rate = len(pauses) / max(char_count, 1)
    pause_fractions = _pause_threshold_fractions(
        flight,
        thresholds=(300.0, 700.0, 1000.0),
    )

    interval_mean, interval_std, interval_min, interval_max = _basic_stats(intervals)

    backspace_count = sum(
        1 for e in ordered_events if e.get("key") == "Backspace" and e.get("event") == "keydown"
    )
    backspace_ratio = backspace_count / max(char_count, 1)

    correction_latencies = _correction_latency(ordered_events)
    correction_latency = float(np.mean(correction_latencies)) if correction_latencies else 0.0

    burstiness = float(flight_std / (flight_mean + 1e-3)) if flight_mean else 0.0
    entropy_dwell = _shannon_entropy(dwell)
    entropy_flight = _shannon_entropy(flight)

    word_gaps = _word_gap_times(ordered_events)
    avg_word_gap = float(np.mean(word_gaps)) if word_gaps else 0.0

    rhythm_smoothness = 0.0
    if len(flight) > 2:
        diffs = np.diff(flight)
        rhythm_smoothness = float(1.0 / (1.0 + np.std(diffs)))

    feature_map: Dict[str, float] = {
        "mean_dwell": dwell_mean,
        "std_dwell": dwell_std,
        "min_dwell": dwell_min,
        "max_dwell": dwell_max,
        "mean_flight": flight_mean,
        "std_flight": flight_std,
        "min_flight": flight_min,
        "max_flight": flight_max,
        "avg_word_gap": avg_word_gap,
        "pause_over_300ms": pause_fractions.get(300.0, 0.0),
        "pause_over_700ms": pause_fractions.get(700.0, 0.0),
        "pause_over_1000ms": pause_fractions.get(1000.0, 0.0),
        "typing_speed": char_count / (total_time / 1000.0),
        "backspace_count": float(backspace_count),
        "backspace_ratio": float(backspace_ratio),
        "correction_latency": correction_latency,
        "burstiness": burstiness,
        "entropy_dwell": entropy_dwell,
        "entropy_flight": entropy_flight,
        "keystroke_count": float(char_count),
        "total_duration_ms": float(total_time),
        "interval_mean": interval_mean,
        "interval_std": interval_std,
        "interval_min": interval_min,
        "interval_max": interval_max,
        "pause_mean": pause_mean,
        "pause_std": pause_std,
        "pause_min": pause_min,
        "pause_max": pause_max,
        "pause_rate": pause_rate,
        "rhythm_smoothness": rhythm_smoothness,
        "monotonic_flag": 1.0 if max(dwell_std, flight_std) < 1e-3 else 0.0,
    }
    return feature_map


def extract_features(
    events: Sequence[Dict],
    *,
    minimum_duration_ms: float = 50.0,
    scaler: Optional[StandardScaler] = None,
    partial_keystrokes: Sequence[int] = (4, 6, 8),
) -> FeatureVector:
    """Extract numeric features from raw key events."""

    if not events:
        raise ValueError("No events supplied")

    ordered = sorted(events, key=lambda e: e["ts"])
    feature_map = _compute_feature_map(ordered, minimum_duration_ms=minimum_duration_ms)
    names = list(feature_map.keys())
    raw = np.array([feature_map[name] for name in names], dtype=float)

    normalized: Optional[np.ndarray] = None
    if scaler is not None:
        normalized = scaler.transform(raw.reshape(1, -1))[0]

    partial_vectors: List[np.ndarray] = []
    if partial_keystrokes:
        total_keydowns = sum(1 for e in ordered if e.get("event") == "keydown")
        for target in partial_keystrokes:
            if target >= total_keydowns:
                break
            subset_events = _slice_events_by_keystrokes(ordered, keydown_target=target)
            if len(subset_events) < 4:
                continue
            try:
                partial_map = _compute_feature_map(subset_events, minimum_duration_ms=minimum_duration_ms)
            except ValueError:
                continue
            partial_vectors.append(np.array([partial_map[name] for name in names], dtype=float))

    return FeatureVector(names=names, raw=raw, normalized=normalized, partials=partial_vectors or None)


__all__ = ["FeatureVector", "extract_features", "TIMING_FEATURE_KEYS"]
