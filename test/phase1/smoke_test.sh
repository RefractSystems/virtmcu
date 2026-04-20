#!/usr/bin/env bash
# test/phase1/smoke_test.sh — Phase 1 smoke test (Modernized to pytest)
set -euo pipefail
pytest tests/test_phase1.py
