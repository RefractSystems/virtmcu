#!/usr/bin/env bash
# test/phase3/smoke_test.sh — Phase 3 smoke test (Modernized to pytest)
set -euo pipefail
pytest tests/test_phase3.py
