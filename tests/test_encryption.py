from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parents[1]))

from backend.utils import encryption


def test_encrypt_decrypt_roundtrip(tmp_path: Path):
    data = {"hello": "world"}
    target = tmp_path / "payload.json"
    encryption.save_encrypted_json(target, data)
    recovered = encryption.load_encrypted_json(target)
    assert recovered == data
