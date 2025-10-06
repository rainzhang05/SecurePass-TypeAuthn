"""FastAPI application for SecurePass-TypeAuthn."""
from __future__ import annotations

import base64
import io
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List

import orjson
import pyotp
import qrcode
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.append(str(ROOT_DIR))

from backend.utils.feature_extraction import extract_features
from backend.utils.storage import (
    delete_user_artifacts,
    get_user_dir,
    list_user_ids,
    load_secret,
    store_secret,
)
from backend.utils.train_model import TrainingResult, add_sample_and_maybe_train
from backend.utils.verify_model import LivenessError, ModelNotTrainedError, verify_sample

FRONTEND_DIR = Path(__file__).resolve().parents[1] / "frontend"


class ORJSONResponse(JSONResponse):
    media_type = "application/json"

    def render(self, content: Dict) -> bytes:
        return orjson.dumps(content)


class EnrollmentStartRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)


class EnrollmentSubmitRequest(BaseModel):
    user_id: str
    events: List[Dict]


class AuthStartRequest(BaseModel):
    user_id: str


class AuthSubmitRequest(BaseModel):
    user_id: str
    events: List[Dict]


class TotpSetupRequest(BaseModel):
    user_id: str


class TotpRevealRequest(BaseModel):
    user_id: str
    auth_token: str


PROMPTS = [
    "Secure typing builds trust in digital worlds.",
    "Behavioral biometrics adds a unique protection layer.",
    "Type naturally; tiny rhythms secure your account.",
]

CHALLENGE = "secure pass authentication"


class SessionStore:
    def __init__(self, ttl_minutes: int = 10):
        self._tokens: Dict[str, Dict[str, str]] = {}
        self.ttl = timedelta(minutes=ttl_minutes)

    def issue(self, user_id: str) -> str:
        token = uuid.uuid4().hex
        expires_at = datetime.utcnow() + self.ttl
        self._tokens[token] = {"user_id": user_id, "expires_at": expires_at.isoformat()}
        return token

    def validate(self, token: str, user_id: str) -> bool:
        payload = self._tokens.get(token)
        if not payload:
            return False
        expires_at = datetime.fromisoformat(payload["expires_at"])
        if datetime.utcnow() > expires_at:
            self._tokens.pop(token, None)
            return False
        return payload.get("user_id") == user_id

    def invalidate(self, token: str) -> None:
        self._tokens.pop(token, None)

    def revoke_user(self, user_id: str) -> None:
        for token in [t for t, payload in self._tokens.items() if payload.get("user_id") == user_id]:
            self._tokens.pop(token, None)


session_store = SessionStore()

app = FastAPI(title="SecurePass-TypeAuthn", default_response_class=ORJSONResponse)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"]
    ,
    allow_headers=["*"],
)

if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


@app.get("/")
def serve_index() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/users")
def list_users() -> Dict[str, List[str]]:
    return {"users": list_user_ids()}


@app.delete("/users/{user_id}")
def delete_user(user_id: str):
    removed = delete_user_artifacts(user_id)
    session_store.revoke_user(user_id)
    if not removed:
        raise HTTPException(status_code=404, detail="User not found")
    return {"deleted": user_id}


@app.post("/enroll/start")
def enroll_start(payload: EnrollmentStartRequest):
    get_user_dir(payload.user_id)
    return {"prompts": PROMPTS, "required_samples": len(PROMPTS)}


@app.post("/enroll/submit")
def enroll_submit(payload: EnrollmentSubmitRequest):
    feature_vector = extract_features(payload.events)
    training = add_sample_and_maybe_train(
        payload.user_id,
        feature_vector.features.tolist(),
        list(feature_vector.names),
        min_samples=len(PROMPTS),
    )
    response: Dict[str, object] = {
        "features": feature_vector.as_dict(),
        "stored_samples": training.samples if isinstance(training, TrainingResult) else None,
    }
    if isinstance(training, TrainingResult):
        response.update(
            {
                "trained": True,
                "threshold": training.threshold,
                "mean_score": training.mean_score,
                "std_score": training.std_score,
            }
        )
    else:
        response.update({"trained": False})
    return response


@app.post("/auth/start")
def auth_start(payload: AuthStartRequest):
    return {"challenge": CHALLENGE}


@app.post("/auth/submit")
def auth_submit(payload: AuthSubmitRequest):
    feature_vector = extract_features(payload.events)
    try:
        result = verify_sample(payload.user_id, feature_vector)
    except ModelNotTrainedError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except LivenessError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    if result["accepted"]:
        auth_token = session_store.issue(payload.user_id)
    else:
        auth_token = None

    return {"result": result, "auth_token": auth_token}


@app.post("/totp/setup")
def totp_setup(payload: TotpSetupRequest):
    secret = load_secret(payload.user_id, "totp")
    if not secret:
        secret = pyotp.random_base32()
        store_secret(payload.user_id, "totp", secret)
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=payload.user_id, issuer_name="SecurePass-TypeAuthn")
    qr = qrcode.QRCode(box_size=4, border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")
    return {"secret": secret, "uri": uri, "qr": qr_b64}


@app.post("/totp/reveal")
def totp_reveal(payload: TotpRevealRequest):
    if not session_store.validate(payload.auth_token, payload.user_id):
        raise HTTPException(status_code=403, detail="Authentication session invalid or expired")
    secret = load_secret(payload.user_id, "totp")
    if not secret:
        raise HTTPException(status_code=404, detail="TOTP not configured")
    totp = pyotp.TOTP(secret)
    return {"code": totp.now()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app:app", host="127.0.0.1", port=8000, reload=False)

