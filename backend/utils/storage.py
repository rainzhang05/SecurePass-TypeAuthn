"""Utility helpers for working with encrypted user storage."""
from __future__ import annotations

import io
import json
import shutil
from pathlib import Path
from typing import Iterable, List, Optional

import pandas as pd

from .encryption import read_encrypted, write_encrypted

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "models"
SECRETS_DIR = BASE_DIR / "secrets"


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
        # Older secrets may have been stored as raw strings; normalize them into JSON.
        payload = {"value": decoded}
        write_json(path, payload)
        return payload


def write_json(path: Path, payload: dict) -> None:
    buffer = json.dumps(payload, indent=2).encode("utf-8")
    write_encrypted(path, buffer)


def load_features(user_id: str) -> pd.DataFrame:
    file_path = get_user_dir(user_id) / "features.csv.enc"
    if not file_path.exists():
        return pd.DataFrame()
    decrypted = read_encrypted(file_path)
    return pd.read_csv(io.BytesIO(decrypted))


def append_features(user_id: str, feature_vector: List[float], feature_names: Iterable[str]) -> pd.DataFrame:
    df = load_features(user_id)
    new_row = pd.DataFrame([list(feature_vector)], columns=list(feature_names))
    df = pd.concat([df, new_row], ignore_index=True)
    buffer = io.BytesIO()
    df.to_csv(buffer, index=False)
    write_encrypted(get_user_dir(user_id) / "features.csv.enc", buffer.getvalue())
    return df


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

