#!/usr/bin/env bash
# test/phase12/smoke_test.sh — Phase 12 smoke test (Modernized to pytest)
set -euo pipefail
pytest tests/test_phase12.py
