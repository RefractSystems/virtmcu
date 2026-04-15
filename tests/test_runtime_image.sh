#!/usr/bin/env bash
# Verifies the API contract of the final virtmcu runtime image.
set -e

IMAGE=$1
if [ -z "$IMAGE" ]; then
    echo "Usage: $0 <runtime_image>"
    exit 1
fi

echo "Verifying runtime image: $IMAGE"

docker run -i --rm -v "$(pwd):/app" "$IMAGE" bash <<'EOF'
    set -e
    echo "1. Checking QEMU binary..."
    which qemu-system-arm > /dev/null || (echo "❌ qemu-system-arm not found" && exit 1)
    
    echo "2. Checking arm-generic-fdt support..."
    qemu-system-arm -M help | grep -q "arm-generic-fdt" || (echo "❌ arm-generic-fdt not supported" && exit 1)

    echo "3. Checking yaml2qemu tool and dtc..."
    which dtc > /dev/null || (echo "❌ dtc not found" && exit 1)
    export PYTHONPATH="/app:$PYTHONPATH"
    python3 -m tools.yaml2qemu --help > /dev/null 2>&1 || (echo "❌ tools.yaml2qemu not found" && exit 1)

    echo "4. Checking virtmcu plugins..."
    if ! find /opt/virtmcu/lib -name "hw-virtmcu-zenoh.so" | grep -q "."; then
        echo "❌ Error: hw-virtmcu-zenoh.so plugin not found"
        exit 1
    fi

    echo "5. Checking Zenoh connectivity (router property)..."
    
    # Create a minimal DTB for arm-generic-fdt
    cat <<DTS > /tmp/minimal.dts
/dts-v1/;
/ {
    model = "test";
    compatible = "test";
    #address-cells = <1>;
    #size-cells = <1>;
    chosen { stdout-path = "/cpus/cpu@0"; };
    cpus {
        #address-cells = <1>;
        #size-cells = <0>;
        cpu@0 { device_type = "cpu"; compatible = "arm,cortex-a15"; reg = <0>; };
    };
};
DTS
    dtc -I dts -O dtb -o /tmp/minimal.dtb /tmp/minimal.dts

    # Start mock router
    python3 /app/tests/zenoh_router_mock.py &
    ROUTER_PID=$!
    
    sleep 2

    # Start QEMU
    timeout 15 qemu-system-arm \
        -M virt -machine dynamic-sysbus=zenoh-clock \
        -display none -m 64M -S \
        -device zenoh-clock,router=tcp/127.0.0.1:7447,node=0 \
        2>&1 | tee /tmp/qemu.log &
    QEMU_PID=$!

    if wait $ROUTER_PID; then
        echo "✅ Zenoh connectivity verified"
    else
        echo "❌ Zenoh connectivity test failed"
        cat /tmp/qemu.log
        kill $QEMU_PID 2>/dev/null || true
        exit 1
    fi
    kill $QEMU_PID 2>/dev/null || true
EOF

echo "✅ Runtime image verification passed!"
