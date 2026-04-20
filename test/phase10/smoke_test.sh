#!/usr/bin/env bash
# test/phase10/smoke_test.sh — Phase 10 smoke test (Modernized to pytest)
set -euo pipefail
pytest tests/test_phase10.py
