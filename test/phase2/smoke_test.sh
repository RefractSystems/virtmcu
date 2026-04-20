#!/usr/bin/env bash
# test/phase2/smoke_test.sh — Phase 2 smoke test (Modernized to pytest)
set -euo pipefail
pytest tests/test_phase2.py
