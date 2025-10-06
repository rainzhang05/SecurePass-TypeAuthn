import base64
import io
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pyotp
import qrcode
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator

from .utils import encryption, feature_extraction, train_model, verify_model

APP_TITLE = "SecurePass-TypeAuthn"
DEFAULT_PROMPTS = [
    "Security is built on trust and timing.",
    "Keystrokes can be as unique as fingerprints.",
    "Machine learning protects modern identities.",
]
CHALLENGE_PHRASES = [
    "Zero trust needs smart typing.",
    "Biometric rhythms verify you.",
    "Fast typing, secure access.",
]

SESSION_TTL_MINUTES = 10

app = FastAPI(title=APP_TITLE, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")


class UserRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=64)

    @field_validator("user_id")
    @classmethod
    def sanitize_user(cls, value: str) -> str:
        if not value.replace("-", "").replace("_", "").isalnum():
            raise ValueError("User identifier must be alphanumeric with optional hyphen/underscore")
        return value


class EnrollmentSubmitRequest(UserRequest):
    session_token: str
    events: List[Dict] = Field(..., description="List of key events")


class AuthenticationSubmitRequest(UserRequest):
    events: List[Dict]
    session_token: Optional[str] = None


class SessionRequest(UserRequest):
    session_token: str


SESSIONS: Dict[str, dict] = {}


def _user_data_dir(user_id: str) -> Path:
    return Path(__file__).resolve().parent / "data" / user_id


def _totp_path(user_id: str) -> Path:
    return _user_data_dir(user_id) / "totp.json"


def _create_session(user_id: str, authenticated: bool = False) -> str:
    token = secrets.token_urlsafe(32)
    SESSIONS[token] = {
        "user_id": user_id,
        "authenticated": authenticated,
        "expires": datetime.now(timezone.utc) + timedelta(minutes=SESSION_TTL_MINUTES),
    }
    return token


def _require_session(user_id: str, session_token: str, authenticated: bool = False) -> dict:
    session = SESSIONS.get(session_token)
    if not session or session["user_id"] != user_id:
        raise HTTPException(status_code=401, detail="Invalid session token")
    if session["expires"] < datetime.now(timezone.utc):
        raise HTTPException(status_code=401, detail="Session expired")
    if authenticated and not session.get("authenticated"):
        raise HTTPException(status_code=403, detail="Authentication required")
    return session


@app.get("/", response_class=HTMLResponse)
async def root() -> HTMLResponse:
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return HTMLResponse(index_path.read_text(encoding="utf-8"))


@app.get("/enroll", response_class=HTMLResponse)
async def enroll_page() -> HTMLResponse:
    path = FRONTEND_DIR / "enroll.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Enrollment UI missing")
    return HTMLResponse(path.read_text(encoding="utf-8"))


@app.get("/authenticate", response_class=HTMLResponse)
async def authenticate_page() -> HTMLResponse:
    path = FRONTEND_DIR / "auth.html"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Authentication UI missing")
    return HTMLResponse(path.read_text(encoding="utf-8"))


@app.post("/enroll/start")
async def enroll_start(request: UserRequest):
    token = _create_session(request.user_id)
    return {"prompts": DEFAULT_PROMPTS, "session_token": token}


@app.post("/enroll/submit")
async def enroll_submit(payload: EnrollmentSubmitRequest):
    session = _require_session(payload.user_id, payload.session_token)
    feature_vector = feature_extraction.extract_features(payload.events)
    if feature_vector.vector[1] == 0.0 and feature_vector.vector[5] == 0.0:
        raise HTTPException(status_code=400, detail="Detected non-human typing pattern")

    train_model.append_feature(payload.user_id, feature_vector.vector, feature_vector.feature_names)
    features_matrix, _ = train_model.load_features(payload.user_id)

    training_summary = None
    if features_matrix.shape[0] >= 3:
        training_summary = train_model.train_user_model(payload.user_id)

    session["authenticated"] = False
    return {
        "samples": int(features_matrix.shape[0]),
        "trained": training_summary is not None,
        "training_summary": training_summary.__dict__ if training_summary else None,
    }


@app.post("/auth/start")
async def auth_start(request: UserRequest):
    token = _create_session(request.user_id)
    phrase = secrets.choice(CHALLENGE_PHRASES)
    return {"challenge": phrase, "session_token": token}


@app.post("/auth/submit")
async def auth_submit(payload: AuthenticationSubmitRequest, request: Request):
    session_token = (
        payload.session_token
        or request.headers.get("X-Session-Token")
        or request.query_params.get("session_token")
    )
    if not session_token:
        raise HTTPException(status_code=400, detail="Missing session token")
    session = _require_session(payload.user_id, session_token)
    feature_vector = feature_extraction.extract_features(payload.events)
    try:
        result = verify_model.evaluate_sample(payload.user_id, feature_vector.vector)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    session["authenticated"] = result.accepted
    session["expires"] = datetime.now(timezone.utc) + timedelta(minutes=SESSION_TTL_MINUTES)
    session["score"] = result.score
    return {
        "accepted": result.accepted,
        "score": result.score,
        "threshold": result.threshold,
    }


@app.post("/totp/setup")
async def totp_setup(payload: SessionRequest):
    session = _require_session(payload.user_id, payload.session_token, authenticated=True)
    path = _totp_path(payload.user_id)
    data = encryption.load_encrypted_json(path, default=None) if path.exists() else None

    if data is None:
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        data = {"secret": secret, "issuer": APP_TITLE}
        encryption.save_encrypted_json(path, data)
    else:
        secret = data["secret"]
        totp = pyotp.TOTP(secret)

    uri = totp.provisioning_uri(name=payload.user_id, issuer_name=APP_TITLE)
    img = qrcode.make(uri)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    qr_base64 = base64.b64encode(buffer.getvalue()).decode("ascii")

    session["totp_secret"] = secret
    return {"secret": secret, "provisioning_uri": uri, "qr_code": qr_base64}


@app.post("/totp/reveal")
async def totp_reveal(payload: SessionRequest):
    session = _require_session(payload.user_id, payload.session_token, authenticated=True)
    path = _totp_path(payload.user_id)
    data = encryption.load_encrypted_json(path, default=None)
    if data is None:
        raise HTTPException(status_code=404, detail="TOTP not configured")
    totp = pyotp.TOTP(data["secret"])
    return {"code": totp.now(), "valid_for": totp.interval}


@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}
