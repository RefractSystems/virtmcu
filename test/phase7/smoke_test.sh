#!/usr/bin/env bash
# test/phase7/smoke_test.sh — Phase 7 smoke test (Modernized to pytest)
set -euo pipefail
pytest tests/test_phase7.py
