#!/usr/bin/env bash
set -euo pipefail

# Argument 1: Path to coverage data directory (defaults to /workspace/all-coverage for CI)
COV_DIR="${1:-/workspace/all-coverage}"

mkdir -p /workspace/test-results
# Ensure the directory exists to avoid gcovr error if no artifacts found
mkdir -p "$COV_DIR"

echo "==> Running gcovr against $COV_DIR..."

gcovr -r /build/qemu/hw/virtmcu \
    --gcov-executable gcov \
    --gcov-ignore-errors=no_working_dir_found \
    --object-directory /build/qemu/build-virtmcu \
    --xml /workspace/test-results/peripheral-coverage.xml \
    --html-details /workspace/test-results/peripheral-coverage.html \
    --print-summary \
    "$COV_DIR"
