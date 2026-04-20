#!/usr/bin/env bash
# test/phase4/smoke_test.sh — Phase 4 smoke test (Modernized to pytest)
set -euo pipefail
pytest tools/testing/test_qmp.py tests/test_qmp_bridge.py tests/test_qemu_library_pytest.py
