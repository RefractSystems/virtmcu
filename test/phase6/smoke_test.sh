#!/usr/bin/env bash
# test/phase6/smoke_test.sh — Phase 6 smoke test (Modernized to pytest)
set -euo pipefail
pytest tests/test_phase6.py
