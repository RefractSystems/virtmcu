#!/bin/bash
set -e

source .venv/bin/activate

echo "==> Building Zenoh Coordinator"
export PATH="$HOME/.cargo/bin:$PATH"
cd tools/zenoh_coordinator && cargo build
cd ../..

echo "==> Running Interactive Echo Test"
pytest tests/test_interactive_echo.robot -v
