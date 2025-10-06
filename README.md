# 🔐 SecurePass-TypeAuthn

SecurePass-TypeAuthn is a complete behavioral biometric authentication prototype
that recognises users based on their keystroke dynamics and protects access with
RFC 6238 compliant TOTP codes. The project showcases an end-to-end workflow
covering enrollment, machine learning model training, authentication, and
second-factor delivery — all running locally.

## ✨ Features

- **FastAPI backend** providing secure REST endpoints for enrollment,
  authentication, and TOTP management.
- **Feature engineering** pipeline that extracts dwell times, flight times,
  typing cadence, and error patterns from raw key events.
- **One-Class SVM** model per user with automatic calibration of acceptance
  thresholds and encrypted persistence.
- **Modern frontend** (vanilla JS + Tailwind-inspired styling) that captures
  high-resolution keystrokes, blocks clipboard abuse, and visualises progress.
- **Encrypted storage** for feature datasets, models, and TOTP secrets using
  AES-based Fernet keys.
- **Dashboard** that reveals live TOTP codes once behavioral authentication
  succeeds, including QR provisioning for authenticator apps.
- **Evaluation tooling** to compute FAR, FRR, accuracy, AUC, and plot ROC curves.

## 🗂️ Project structure

```
SecurePass-TypeAuthn/
├─ backend/
│  ├─ app.py                     # FastAPI application
│  └─ utils/
│     ├─ encryption.py           # Fernet helpers
│     ├─ feature_extraction.py   # Keystroke feature engineering
│     ├─ train_model.py          # Dataset handling + model training
│     └─ verify_model.py         # Authentication scoring
├─ frontend/
│  ├─ index.html                 # Landing page
│  ├─ enroll.html                # Enrollment UI
│  ├─ auth.html                  # Authentication dashboard
│  ├─ js/
│  │  ├─ api.js
│  │  ├─ enroll.js
│  │  └─ auth.js
│  └─ css/style.css
├─ reports/                      # Evaluation artefacts
├─ tests/                        # Pytest suite
├─ evaluate_model.py             # Metrics + ROC reporting
├─ requirements.txt
└─ run.sh                        # Helper to launch the server
```

## 🚀 Getting started

1. **Install dependencies**

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```

2. **Run the backend**

   ```bash
   ./run.sh
   ```

3. **(Optional) Rebuild the demo model**

   Binary artefacts are intentionally excluded from the repository. To evaluate
   the pre-recorded demo user, regenerate the encrypted model and threshold by
   running:

   ```bash
   python bootstrap_demo.py
   ```

   This consumes the synthetic feature dataset stored in
   `backend/data/demo/features.csv` and writes fresh encrypted artefacts under
   `backend/models/demo/`.

4. **Open the UI**

   Visit [http://localhost:8000](http://localhost:8000) and use the navigation
   to enroll or authenticate.

## 📝 Workflow

1. **Enrollment**
   - Enter a user ID and click *Start enrollment*.
   - Type the displayed prompts (3 samples recommended). Each submission stores
     encrypted feature vectors and, after ≥3 samples, automatically trains the
     user-specific One-Class SVM model.
2. **Authentication**
   - Request a challenge phrase, type it, and submit. The backend extracts
     features, scores them against the trained model, and returns a confidence
     score.
3. **TOTP dashboard**
   - Successful authentication unlocks the dashboard, generates/loads the TOTP
     secret, displays a QR code for authenticator apps, and continuously shows
     the current 6-digit code.

The entire process respects the typing duration constraints (≈2 minutes for
enrollment, ≈5 seconds for authentication per attempt).

## 📊 Model evaluation

Use the evaluation script to compute accuracy, FAR, FRR, EER, and ROC curves
after at least one user has a trained model (for example by enrolling through
the UI or running `python bootstrap_demo.py`):

```bash
python evaluate_model.py
```

Results are stored in `reports/metrics.json` and corresponding ROC plots are
saved under `reports/roc_<user>.png`.

## 🔐 Security highlights

- All feature datasets, trained models, and TOTP secrets are encrypted at rest
  using Fernet symmetric encryption.
- Basic liveness detection rejects perfectly uniform timing patterns indicative
  of scripted input.
- Clipboard interactions (copy, paste, cut, context menu) are blocked during
  typing to maintain data integrity.
- Sessions are short-lived and required for every privileged action (training,
  verification, TOTP retrieval).
- A demo encryption key (`backend/.secret.key`) ships with the repository so the
  synthetic dataset can be decrypted; replace it in production environments.

## 🧪 Testing

Run the automated tests to validate critical utilities:

```bash
pytest
```

## 📚 API reference

| Endpoint | Method | Description |
| --- | --- | --- |
| `/enroll/start` | POST | Creates an enrollment session and returns prompts. |
| `/enroll/submit` | POST | Accepts keystroke events, stores features, trains model. |
| `/auth/start` | POST | Issues an authentication challenge and session token. |
| `/auth/submit` | POST | Scores a sample and returns acceptance decision. |
| `/totp/setup` | POST | Generates or loads the TOTP secret + QR code. |
| `/totp/reveal` | POST | Returns the current 6-digit TOTP code. |
| `/health` | GET | Basic health probe. |

Each request expects a `user_id`; session-based endpoints also require the
`session_token` issued by the corresponding start/authenticate calls.

## 📄 License

This project is released under the MIT License. See [LICENSE](LICENSE) for
details.
