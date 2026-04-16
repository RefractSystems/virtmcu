#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"

# 1. Generate DTB and CLI args from YAML
cd "$WORKSPACE_DIR"
python3 -m tools.yaml2qemu "test/phase12/test_telemetry.yaml" --out-dtb "test/phase12/test_telemetry.dtb" --out-cli "test/phase12/test_telemetry.cli" --out-arch "test/phase12/test_telemetry.arch"

ARCH=$(cat "$SCRIPT_DIR/test_telemetry.arch")
CLI_ARGS=$(cat "$SCRIPT_DIR/test_telemetry.cli")
DTB_FILE="$SCRIPT_DIR/test_telemetry.dtb"

# 2. Start the Telemetry listener in the background
LOG_FILE="$SCRIPT_DIR/telemetry.log"
PYTHONUNBUFFERED=1 python3 -u "$WORKSPACE_DIR/tools/telemetry_listener.py" 0 > "$LOG_FILE" 2>&1 &
LISTENER_PID=$!

# Give listener a moment to start and register queryables
sleep 1

# 3. Run QEMU for a short duration with the telemetry plugin
echo "Starting QEMU..."
timeout 2s "$WORKSPACE_DIR/scripts/run.sh" \
    --dtb "$DTB_FILE" \
    $CLI_ARGS \
    -kernel "$SCRIPT_DIR/test_wfi.elf" \
    -nographic \
    -serial null -monitor null || true

# 4. Stop the listener
kill -TERM "$LISTENER_PID" || true
wait "$LISTENER_PID" || true

# 5. Analyze the log
echo "=== Telemetry Log ==="
cat "$LOG_FILE"
echo "====================="

FAIL=0
if ! grep -q "CPU_STATE" "$LOG_FILE"; then
    echo "FAIL: Did not find CPU_STATE events."
    FAIL=1
fi
if ! grep -q "IRQ" "$LOG_FILE"; then
    echo "FAIL: Did not find IRQ events."
    FAIL=1
fi

if [ $FAIL -eq 0 ]; then
    echo "Phase 12 Telemetry smoke test PASSED!"
    exit 0
else
    echo "Phase 12 Telemetry smoke test FAILED!"
    exit 1
fi
