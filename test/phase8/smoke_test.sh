#!/usr/bin/env bash
# test/phase8/smoke_test.sh — Phase 8 smoke test (Modernized to pytest)
set -euo pipefail
pytest tests/test_phase8.py
