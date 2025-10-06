"""Utility functions for encrypting and decrypting application data.

All persistent data within the SecurePass-TypeAuthn backend is encrypted at rest
using the Fernet symmetric encryption scheme provided by the cryptography
library.  These helpers provide a thin abstraction around Fernet so the rest of
codebase can remain agnostic of the persistence details.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from cryptography.fernet import Fernet


_SECRET_PATH = Path(__file__).resolve().parent.parent / ".secret.key"


def _load_or_create_key() -> bytes:
    """Load the encryption key from disk, creating it if necessary."""
    if not _SECRET_PATH.exists():
        _SECRET_PATH.write_bytes(Fernet.generate_key())
    return _SECRET_PATH.read_bytes()


def get_fernet() -> Fernet:
    """Return a Fernet instance using the application key."""
    return Fernet(_load_or_create_key())


def encrypt_bytes(data: bytes) -> bytes:
    """Encrypt arbitrary bytes."""
    return get_fernet().encrypt(data)


def decrypt_bytes(token: bytes) -> bytes:
    """Decrypt arbitrary bytes."""
    return get_fernet().decrypt(token)


def save_encrypted_json(path: Path, payload: Any) -> None:
    """Serialise *payload* as JSON and persist it encrypted at *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2)
    path.write_bytes(encrypt_bytes(data.encode("utf-8")))


def load_encrypted_json(path: Path, default: Any | None = None) -> Any:
    """Load an encrypted JSON payload from *path*.

    Args:
        path: Target path.
        default: Value returned if the file does not exist.
    """
    if not path.exists():
        return default
    decrypted = decrypt_bytes(path.read_bytes()).decode("utf-8")
    return json.loads(decrypted)


def save_encrypted_text(path: Path, text: str) -> None:
    """Persist text content encrypted at *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encrypt_bytes(text.encode("utf-8")))


def load_encrypted_text(path: Path) -> str:
    """Read encrypted text content from *path*."""
    return decrypt_bytes(path.read_bytes()).decode("utf-8")


def save_encrypted_bytes(path: Path, data: bytes) -> None:
    """Persist binary data encrypted at *path*."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encrypt_bytes(data))


def load_encrypted_bytes(path: Path) -> bytes:
    """Load encrypted binary data from *path*."""
    return decrypt_bytes(path.read_bytes())
