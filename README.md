# 🔐 SecurePass-TypeAuthn

SecurePass-TypeAuthn is an end-to-end behavioral biometric authentication prototype that learns a user's typing rhythm to protect access to sensitive resources. The platform captures keystroke dynamics during enrollment, trains an AI model with encrypted storage, and verifies subsequent logins before revealing time-based one-time passwords (TOTP).

## ✨ Features

- **FastAPI backend** with encrypted data/model storage using AES (Fernet) encryption.
- **Behavioral biometrics** via keystroke dynamics, extracting dwell/flight times, pauses, error rates, and liveness checks.
- **One-Class SVM pipeline** with automatic threshold calibration targeting ≥95% accuracy, FAR ≤1%, FRR ≤5%.
- **Responsive frontend** for enrollment, authentication, and TOTP onboarding with real-time keystroke capture.
- **RFC 6238 TOTP** generation with QR enrollment and secure reveal after successful authentication.
- **Metrics tooling** to evaluate accuracy, FAR, FRR, and EER with synthetic impostor analysis.
- **Pytest suite** covering feature extraction logic.

## 🗂️ Project Structure

```
securepass-typeauthn/
├─ backend/
│  ├─ app.py
│  ├─ data/
│  ├─ models/
│  ├─ secrets/
│  └─ utils/
│     ├─ encryption.py
│     ├─ feature_extraction.py
│     ├─ storage.py
│     ├─ train_model.py
│     └─ verify_model.py
├─ frontend/
│  ├─ index.html
│  ├─ enroll.html
│  ├─ auth.html
│  ├─ css/style.css
│  └─ js/
│     ├─ api.js
│     ├─ enroll.js
│     └─ auth.js
├─ reports/
├─ tests/
│  └─ test_feature_extraction.py
├─ evaluate_model.py
├─ requirements.txt
├─ LICENSE
└─ README.md
```

## 🚀 Getting Started

### Prerequisites

- Python 3.11+
- Node is **not** required; frontend assets are static.

### Installation

#### Create a virtual environment

- **macOS / Linux**

  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

- **Windows (PowerShell)**

  ```powershell
  py -3 -m venv .venv
  .\.venv\Scripts\Activate.ps1
  ```

#### Install dependencies

- **macOS / Linux**

  ```bash
  pip install -r requirements.txt
  ```

- **Windows (PowerShell)**

  ```powershell
  pip install -r requirements.txt
  ```

### Running the Stack

- **macOS / Linux**

  ```bash
  python backend/app.py
  ```

- **Windows (PowerShell)**

  ```powershell
  python backend/app.py
  ```

Open [http://localhost:8000](http://localhost:8000) to access the web UI. Static assets are served directly by FastAPI.

## 🧪 Workflow

1. **Enrollment**
   - Navigate to `/static/enroll.html` (or use the homepage link).
   - Enter a unique user ID and complete the typing prompts (≈2 minutes total).
   - After three prompts, the system trains a personalized One-Class SVM and displays a QR code + secret for TOTP onboarding.

2. **Authentication**
   - Go to `/static/auth.html`.
   - Enter the same user ID, start authentication, and type the challenge phrase (≈5 seconds).
   - If the keystroke signature matches, you'll see `Verified ✅` and can request the current TOTP code.

3. **Two-Factor Verification**
   - Scan the QR code in Google Authenticator, 1Password, Authy, etc., or manually enter the shared secret.
   - After a successful authentication the backend returns the active 6-digit TOTP code.

## 📊 Model Evaluation

Run the evaluator after training users to generate metrics under `reports/metrics.json`:

```bash
python evaluate_model.py
cat reports/metrics.json
```

The evaluation reports per-user accuracy, false acceptance rate (FAR), false rejection rate (FRR), and equal error rate (EER) using synthetic impostor samples.

## 🔒 Security Notes

- All captured keystroke features, trained models, and TOTP secrets are encrypted on disk via Fernet AES-128.
- Liveness checks reject perfectly uniform timing profiles that could indicate automation.
- The frontend blocks clipboard operations and context menus during typing challenges.
- The backend sanitizes payloads and enforces per-user storage isolation.

## 🧰 Testing

```bash
pytest
```

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.

