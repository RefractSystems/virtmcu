#!/bin/bash
set -e

# Test the interactive echo firmware using QMP and the new write_to_uart functionality

source .venv/bin/activate
pytest tests/test_qmp_keywords.robot -v
