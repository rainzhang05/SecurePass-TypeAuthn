"""Utilities for encrypting and decrypting files using Fernet symmetric encryption."""
from __future__ import annotations

import base64
import os
from pathlib import Path
from typing import Union

from cryptography.fernet import Fernet


_DEFAULT_KEY_PATH = Path(__file__).resolve().parents[1] / "secret.key"


def _generate_key() -> bytes:
    """Generate a new Fernet key."""
    return Fernet.generate_key()


def load_or_create_key(key_path: Union[str, os.PathLike] = _DEFAULT_KEY_PATH) -> bytes:
    """Load the Fernet key from disk, creating it if necessary."""
    path = Path(key_path)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        key = _generate_key()
        path.write_bytes(key)
        return key
    key = path.read_bytes().strip()
    if not key:
        key = _generate_key()
        path.write_bytes(key)
    try:
        # Validate key by attempting to base64 decode it
        base64.urlsafe_b64decode(key)
    except Exception as exc:  # pragma: no cover - defensive
        raise ValueError("Invalid encryption key on disk") from exc
    return key


def get_cipher(key_path: Union[str, os.PathLike] = _DEFAULT_KEY_PATH) -> Fernet:
    """Return a Fernet cipher instance using the key at ``key_path``."""
    key = load_or_create_key(key_path)
    return Fernet(key)


def encrypt_bytes(data: bytes, key_path: Union[str, os.PathLike] = _DEFAULT_KEY_PATH) -> bytes:
    """Encrypt ``data`` using the configured Fernet key."""
    cipher = get_cipher(key_path)
    return cipher.encrypt(data)


def decrypt_bytes(token: bytes, key_path: Union[str, os.PathLike] = _DEFAULT_KEY_PATH) -> bytes:
    """Decrypt ``token`` using the configured Fernet key."""
    cipher = get_cipher(key_path)
    return cipher.decrypt(token)


def write_encrypted(path: Union[str, os.PathLike], data: bytes, *, key_path: Union[str, os.PathLike] = _DEFAULT_KEY_PATH) -> None:
    """Encrypt ``data`` and write it to ``path``."""
    encrypted = encrypt_bytes(data, key_path=key_path)
    Path(path).write_bytes(encrypted)


def read_encrypted(path: Union[str, os.PathLike], *, key_path: Union[str, os.PathLike] = _DEFAULT_KEY_PATH) -> bytes:
    """Read encrypted data from ``path`` and decrypt it."""
    return decrypt_bytes(Path(path).read_bytes(), key_path=key_path)

