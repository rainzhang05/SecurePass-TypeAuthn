from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from sklearn import metrics

from backend.utils import train_model, verify_model


REPORTS_DIR = Path(__file__).resolve().parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


def evaluate_user(user_id: str) -> dict:
    features, _ = train_model.load_features(user_id)
    pipeline = verify_model.load_pipeline(user_id)
    threshold_info = verify_model.load_threshold(user_id)
    threshold = float(threshold_info["threshold"])

    genuine_scores = pipeline.decision_function(features)
    genuine_accept = genuine_scores >= threshold
    frr = 1.0 - float(np.mean(genuine_accept))

    rng = np.random.default_rng(42)
    noise_scale = np.std(features, axis=0, ddof=1) + 1e-3
    impostor_samples = features.mean(axis=0) + rng.normal(0, noise_scale, size=(features.shape[0] * 5, features.shape[1]))
    impostor_scores = pipeline.decision_function(impostor_samples)
    far = float(np.mean(impostor_scores >= threshold))

    labels = np.concatenate([np.ones_like(genuine_scores), np.zeros_like(impostor_scores)])
    all_scores = np.concatenate([genuine_scores, impostor_scores])

    fpr, tpr, _ = metrics.roc_curve(labels, all_scores)
    auc = float(metrics.auc(fpr, tpr))

    accuracy = float(
        (
            np.sum(genuine_scores >= threshold) + np.sum(impostor_scores < threshold)
        )
        / (genuine_scores.size + impostor_scores.size)
    )

    eer_index = int(np.nanargmin(np.abs(fpr - (1 - tpr))))
    eer = float((fpr[eer_index] + (1 - tpr[eer_index])) / 2)

    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(fpr, tpr, label=f"ROC (AUC={auc:.2f})")
    ax.plot([0, 1], [0, 1], linestyle="--", color="grey")
    ax.set_title(f"ROC Curve · {user_id}")
    ax.set_xlabel("False Positive Rate")
    ax.set_ylabel("True Positive Rate")
    ax.legend(loc="lower right")
    fig.tight_layout()
    plot_path = REPORTS_DIR / f"roc_{user_id}.png"
    fig.savefig(plot_path)
    plt.close(fig)

    return {
        "user_id": user_id,
        "samples": int(features.shape[0]),
        "threshold": threshold,
        "mean_score": float(np.mean(genuine_scores)),
        "std_score": float(np.std(genuine_scores)),
        "accuracy": accuracy,
        "far": far,
        "frr": frr,
        "eer": eer,
        "auc": auc,
        "roc_curve": plot_path.name,
    }


def main():
    models_dir = Path(__file__).resolve().parent / "backend" / "models"
    metrics_report = []
    for user_dir in models_dir.iterdir():
        if not user_dir.is_dir():
            continue
        user_id = user_dir.name
        try:
            summary = evaluate_user(user_id)
            metrics_report.append(summary)
            print(f"Evaluated {user_id}: accuracy={summary['accuracy']:.3f} FAR={summary['far']:.3f} FRR={summary['frr']:.3f}")
        except Exception as exc:  # pragma: no cover - evaluation diagnostics
            print(f"Skipping {user_id}: {exc}")

    report_path = REPORTS_DIR / "metrics.json"
    report_path.write_text(json.dumps(metrics_report, indent=2))
    print(f"Metrics written to {report_path}")


if __name__ == "__main__":
    main()
