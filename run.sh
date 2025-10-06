#!/usr/bin/env bash
set -euo pipefail

uvicorn backend.app:app --reload --host 0.0.0.0 --port 8000
