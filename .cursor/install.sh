#!/usr/bin/env bash
# Idempotent development-environment bootstrap for Vista Turbo HASS.
#
# Provisions the toolchain used by the CI test matrix (.github/workflows/tests.yml):
#   - Python 3.13 for the vista128_bridge unittest suite
#   - Node 22 (provided by the base image) + Playwright Chromium for the
#     frontend keypad-card render tests
#
# Safe to run repeatedly: each step is guarded or naturally idempotent.
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

echo "==> Ensuring Python 3.13 (matches CI test matrix)"
if ! command -v python3.13 >/dev/null 2>&1; then
  sudo add-apt-repository -y ppa:deadsnakes/ppa
  sudo apt-get update
  sudo apt-get install -y python3.13 python3.13-venv
fi
python3.13 -m ensurepip --upgrade >/dev/null
python3.13 -m pip install --quiet --upgrade pip

echo "==> Installing vista128_bridge Python dependencies"
python3.13 -m pip install --quiet -r vista128_bridge/requirements.txt

echo "==> Installing frontend test dependencies"
cd frontend
npm install --no-audit --no-fund
npx playwright install --with-deps chromium

echo "==> Development environment ready"
