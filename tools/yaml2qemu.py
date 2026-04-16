#!/usr/bin/env python3
# ==============================================================================
# yaml2qemu.py
#
# Parses the virtmcu YAML hardware description and translates it into a
# QEMU Device Tree (.dtb). This drives the FdtEmitter using the modern schema.
# ==============================================================================

import argparse
import os
import subprocess
import sys

import yaml

from .repl2qemu.fdt_emitter import FdtEmitter, compile_dtb
from .repl2qemu.parser import ReplDevice, ReplInterrupt, ReplPlatform


def validate_dtb_content(dtb_path: str, expected_peripherals: list[str]):
    """
    Decompiles the DTB and verifies that all expected peripherals are present as nodes.
    """
    try:
        result = subprocess.run(["dtc", "-I", "dtb", "-O", "dts", dtb_path], check=True, capture_output=True, text=True)
        dts_content = result.stdout

        missing = []
        for p in expected_peripherals:
            # Look for node definitions like "name@address {" or "name {"
            # We use a simple string check first; a more robust one would use regex.
            if f"{p}@" not in dts_content and f"{p} " not in dts_content:
                missing.append(p)

        if missing:
            print(
                f"ERROR: The following peripherals from YAML are missing in the generated DTB: {', '.join(missing)}",
                file=sys.stderr,
            )
            # Log the DTS for debugging
            # print("--- GENERATED DTS ---", file=sys.stderr)
            # print(dts_content, file=sys.stderr)
            return False
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error decompiling DTB for validation: {e.stderr}", file=sys.stderr)
        return False


def parse_yaml_platform(yaml_path: str) -> tuple[ReplPlatform, list[str]]:
    """
    Parses our modern YAML schema and returns a ReplPlatform AST and a list of peripheral names.
    """
    with open(yaml_path, "r") as f:
        data = yaml.safe_load(f)

    platform = ReplPlatform()
    peripheral_names = []

    # 1. Map CPUs
    for cpu in data.get("machine", {}).get("cpus", []):
        cpu_name = cpu["name"]
        cpu_type = cpu["type"]
        internal_type = "CPU.ARMv7A"
        if "riscv" in cpu_type.lower():
            internal_type = "CPU.RISCV64"

        dev = ReplDevice(
            name=cpu_name,
            type_name=internal_type,
            address_str="sysbus",
            properties={"cpuType": cpu_type},
        )
        if internal_type == "CPU.RISCV64":
            if "isa" in cpu:
                dev.properties["isa"] = cpu["isa"]
            if "mmu-type" in cpu:
                dev.properties["mmu-type"] = cpu["mmu-type"]

        platform.devices.append(dev)
        # Note: CPUs are handled specially in FdtEmitter, usually under 'cpus' node

    # 2. Map Peripherals
    for p in data.get("peripherals", []):
        name = p["name"]
        # Support both 'renode_type' (for migrated files) or 'type' (for native ones)
        type_name = p.get("type") or p.get("renode_type", "Unknown")

        addr_val = p.get("address", "none")
        address_str = hex(addr_val) if isinstance(addr_val, int) else str(addr_val)

        dev = ReplDevice(name=name, type_name=type_name, address_str=address_str, properties=p.get("properties", {}))

        # Parse interrupts if they exist
        for irq_entry in p.get("interrupts", []):
            if isinstance(irq_entry, int):
                # Native YAML format: just the IRQ number
                dev.interrupts.append(ReplInterrupt("0", "none", str(irq_entry)))
            elif isinstance(irq_entry, str) and "@" in irq_entry:
                # Legacy repl2yaml format: target@line
                target, line = irq_entry.split("@")
                dev.interrupts.append(ReplInterrupt("0", target, line))

        platform.devices.append(dev)
        peripheral_names.append(name)

    return platform, peripheral_names


def main():
    parser = argparse.ArgumentParser(description="Convert virtmcu YAML to Device Tree")
    parser.add_argument("input", help="Path to .yaml file")
    parser.add_argument("--out-dtb", help="Path to output .dtb file", required=True)
    parser.add_argument("--out-cli", help="Path to output .cli file for extra arguments")
    parser.add_argument("--out-arch", help="Path to output .arch file containing target architecture")
    parser.add_argument("--no-validate", action="store_true", help="Skip DTB content validation")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found.")
        sys.exit(1)

    print(f"Parsing YAML: {args.input}...")
    platform, expected_peripherals = parse_yaml_platform(args.input)

    # Extract architecture
    emitter = FdtEmitter(platform)
    arch = emitter.arch
    if args.out_arch:
        with open(args.out_arch, "w") as f:
            f.write(arch)

    # Extract chardev backends which cannot go into the DTB
    cli_args = []
    filtered_devices = []
    dtb_peripherals = []

    for dev in platform.devices:
        if dev.type_name == "zenoh-chardev":
            # Extract to CLI string
            node = dev.properties.get("node", "0")
            chardev_id = dev.properties.get("id", f"chr_{dev.name}")
            cli_args.append("-chardev")
            cli_args.append(f"zenoh,id={chardev_id},node={node}")

            # Since FdtEmitter hardcodes `chardev = <0x00>;` for UARTs,
            # we must also map this chardev to the first available serial port
            cli_args.append("-serial")
            cli_args.append(f"chardev:{chardev_id}")
            # zenoh-chardev is NOT expected in DTB
        else:
            filtered_devices.append(dev)
            if "CPU" not in dev.type_name:
                dtb_peripherals.append(dev.name)

    platform.devices = filtered_devices

    print(f"Generating Device Tree for {len(platform.devices)} devices...")
    dts = emitter.generate_dts()

    if args.out_cli and cli_args:
        with open(args.out_cli, "w") as f:
            for arg in cli_args:
                f.write(arg + "\n")

    print(f"Compiling into '{args.out_dtb}'...")
    if compile_dtb(dts, args.out_dtb):
        print("✓ Compilation successful.")

        if not args.no_validate:
            print("Validating DTB content...")
            if validate_dtb_content(args.out_dtb, dtb_peripherals):
                print("✓ Validation successful.")
            else:
                print("FAILED: DTB validation failed.")
                sys.exit(1)
        else:
            print("! Skipping validation.")
    else:
        print("FAILED: Compilation failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
