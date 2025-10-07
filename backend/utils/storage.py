"""Utility helpers for working with encrypted user storage."""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import pandas as pd

from .encryption import read_encrypted, write_encrypted

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "models"
SECRETS_DIR = BASE_DIR / "secrets"

FEATURES_FILE = "features.csv"
CONFIDENCE_LOG = "confidence.json"
METADATA_COLUMNS = ["session_id", "timestamp", "checksum"]

for directory in (DATA_DIR, MODEL_DIR, SECRETS_DIR):
    directory.mkdir(parents=True, exist_ok=True)


def get_user_dir(user_id: str) -> Path:
    path = DATA_DIR / user_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_user_model_dir(user_id: str) -> Path:
    path = MODEL_DIR / user_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_user_ids() -> List[str]:
    """Return identifiers that currently have trained model artifacts."""
    if not MODEL_DIR.exists():
        return []
    users: List[str] = []
    for user_dir in MODEL_DIR.iterdir():
        if user_dir.is_dir() and any(user_dir.iterdir()):
            users.append(user_dir.name)
    return sorted(users)


def _read_encrypted_csv(path: Path) -> pd.DataFrame:
    decrypted = read_encrypted(path)
    return pd.read_csv(io.BytesIO(decrypted))


def _write_encrypted_csv(path: Path, df: pd.DataFrame) -> None:
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False)
    write_encrypted(path, buffer.getvalue())


def _compute_checksum(feature_vector: Sequence[float], feature_names: Sequence[str]) -> str:
    payload = ",".join(f"{name}:{float(value):.6f}" for name, value in zip(feature_names, feature_vector))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class UserDatasetManager:
    """Manage per-user datasets with metadata and integrity checks."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.user_dir = get_user_dir(user_id)
        self.file_path = self.user_dir / FEATURES_FILE

    def load(self, *, include_metadata: bool = False) -> pd.DataFrame:
        if not self.file_path.exists():
            return pd.DataFrame()
        df = _read_encrypted_csv(self.file_path)
        if include_metadata:
            for column in METADATA_COLUMNS:
                if column not in df.columns:
                    df[column] = None
            return df
        return df.drop(columns=[c for c in METADATA_COLUMNS if c in df.columns], errors="ignore")

    def append(
        self,
        feature_vector: Sequence[float],
        feature_names: Sequence[str],
        *,
        session_id: Optional[str] = None,
        timestamp: Optional[datetime] = None,
        checksum: Optional[str] = None,
        enforce_unique: bool = True,
    ) -> pd.DataFrame:
        feature_names = list(feature_names)
        checksum = checksum or _compute_checksum(feature_vector, feature_names)
        session_id = session_id or uuid.uuid4().hex
        timestamp = timestamp or datetime.utcnow()

        df_full = self.load(include_metadata=True)
        if not df_full.empty and enforce_unique and "checksum" in df_full.columns:
            if checksum in set(df_full["checksum"].dropna()):
                # Duplicate sample detected; return without modification.
                return df_full.drop(columns=[c for c in METADATA_COLUMNS if c in df_full.columns], errors="ignore")

        row = {name: float(value) for name, value in zip(feature_names, feature_vector)}
        for column in METADATA_COLUMNS:
            if column not in df_full.columns:
                df_full[column] = None
        row.update(
            {
                "session_id": session_id,
                "timestamp": timestamp.isoformat(),
                "checksum": checksum,
            }
        )
        df_full = pd.concat([df_full, pd.DataFrame([row])], ignore_index=True)
        _write_encrypted_csv(self.file_path, df_full)
        return df_full.drop(columns=[c for c in METADATA_COLUMNS if c in df_full.columns], errors="ignore")

    def verify_integrity(self) -> bool:
        df = self.load(include_metadata=True)
        if df.empty:
            return True
        if "checksum" not in df.columns:
            return False
        feature_cols = [c for c in df.columns if c not in METADATA_COLUMNS]
        for _, row in df.iterrows():
            checksum = row.get("checksum")
            values = [row.get(col, 0.0) for col in feature_cols]
            expected = _compute_checksum(values, feature_cols)
            if checksum != expected:
                return False
        return True

    def metadata(self) -> pd.DataFrame:
        df = self.load(include_metadata=True)
        if df.empty:
            return df
        return df[[c for c in METADATA_COLUMNS if c in df.columns]]


def get_dataset_manager(user_id: str) -> UserDatasetManager:
    return UserDatasetManager(user_id)


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    data = read_encrypted(path)
    decoded = data.decode("utf-8").strip()
    if not decoded:
        return {}
    try:
        return json.loads(decoded)
    except json.JSONDecodeError:
        payload = {"value": decoded}
        write_json(path, payload)
        return payload


def write_json(path: Path, payload: dict) -> None:
    buffer = json.dumps(payload, indent=2).encode("utf-8")
    write_encrypted(path, buffer)


def load_features(user_id: str, *, include_metadata: bool = False) -> pd.DataFrame:
    manager = get_dataset_manager(user_id)
    df = manager.load(include_metadata=include_metadata)
    return df


def append_features(
    user_id: str,
    feature_vector: Sequence[float],
    feature_names: Iterable[str],
    *,
    session_id: Optional[str] = None,
    timestamp: Optional[datetime] = None,
    checksum: Optional[str] = None,
) -> pd.DataFrame:
    manager = get_dataset_manager(user_id)
    return manager.append(
        feature_vector,
        list(feature_names),
        session_id=session_id,
        timestamp=timestamp,
        checksum=checksum,
    )


def save_model_artifact(user_id: str, filename: str, data: bytes) -> Path:
    model_dir = get_user_model_dir(user_id)
    path = model_dir / filename
    write_encrypted(path, data)
    return path


def load_model_artifact(user_id: str, filename: str) -> Optional[bytes]:
    path = get_user_model_dir(user_id) / filename
    if not path.exists():
        return None
    return read_encrypted(path)


def append_confidence_log(user_id: str, entry: dict) -> None:
    model_dir = get_user_model_dir(user_id)
    path = model_dir / CONFIDENCE_LOG
    existing: List[dict] = []
    if path.exists():
        try:
            existing = read_json(path).get("entries", [])
        except json.JSONDecodeError:
            existing = []
    existing.append(entry)
    write_json(path, {"entries": existing})


def store_secret(user_id: str, name: str, value: str) -> None:
    secrets_dir = SECRETS_DIR / user_id
    secrets_dir.mkdir(parents=True, exist_ok=True)
    path = secrets_dir / f"{name}.json"
    write_json(path, {"value": value})


def load_secret(user_id: str, name: str) -> Optional[str]:
    path = SECRETS_DIR / user_id / f"{name}.json"
    if not path.exists():
        return None
    payload = read_json(path)
    return payload.get("value")


def delete_user_artifacts(user_id: str) -> bool:
    """Remove stored data, models, and secrets for ``user_id``."""
    existed = False
    for base in (DATA_DIR, MODEL_DIR, SECRETS_DIR):
        target = base / user_id
        if target.exists():
            existed = True
            shutil.rmtree(target, ignore_errors=True)
    return existed
