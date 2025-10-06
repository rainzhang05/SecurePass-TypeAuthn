"""Bootstrap helper to regenerate the encrypted demo model artifacts.

Running this script will read the synthetic demo feature dataset stored in
``backend/data/demo/features.csv`` and retrain the associated One-Class SVM
model. The resulting encrypted model and threshold files are written back under
``backend/models/demo/``.
"""
from __future__ import annotations

from pathlib import Path

from backend.utils import train_model


def main() -> None:
    user_id = "demo"
    try:
        summary = train_model.train_user_model(user_id)
    except FileNotFoundError as exc:
        raise SystemExit(
            "Demo features are missing. Ensure backend/data/demo/features.csv exists"
        ) from exc
    except ValueError as exc:
        raise SystemExit(f"Unable to train demo model: {exc}") from exc
    else:
        model_dir = Path(__file__).resolve().parent / "backend" / "models" / user_id
        print(
            "Demo model trained successfully. Artifacts stored in",
            model_dir,
        )
        print(
            f"Samples: {summary.samples}, threshold: {summary.threshold:.4f}, "
            f"mean score: {summary.mean_score:.6f}, std: {summary.std_score:.6f}"
        )


if __name__ == "__main__":
    main()
