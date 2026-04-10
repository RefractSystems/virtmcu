# virtmcu hardware peripheral modules.
#
# This file lives at hw/meson.build inside the virtmcu repo.
# scripts/setup-qemu.sh creates a symlink:
#   <qemu-src>/hw/virtmcu  →  <virtmcu-repo>/hw
# and appends `subdir('virtmcu')` to <qemu-src>/hw/meson.build.
#
# With --enable-modules each entry in hw_virtmcu_modules compiles to a
# standalone shared library (hw-virtmcu-<name>.so / .dylib) placed in the
# QEMU module dir.  Without modules it is linked statically into qemu-system-*.
#
# Adding a new device:
#   1. Create hw/<name>/<name>.c following the pattern in hw/dummy/dummy.c.
#   2. Add a source_set and register it below.

hw_virtmcu_modules = {}

# ── dummy ─────────────────────────────────────────────────────────────────────
# Minimal QOM SysBusDevice.  Always included — it is the smoke-test for the
# dynamic loading pipeline and the template for all new devices.
dummy_ss = ss.source_set()
dummy_ss.add(files('dummy/dummy.c'))
hw_virtmcu_modules += {'dummy': dummy_ss}

# ── mmio-socket-bridge ────────────────────────────────────────────────────────
# Path A co-simulation bridge: forwards MMIO reads/writes over a Unix socket to
# an external process (e.g. the SystemC adapter in tools/systemc_adapter/).
# Compiles to hw-virtmcu-mmio-socket-bridge.so.
mmio_bridge_ss = ss.source_set()
mmio_bridge_ss.add(files('misc/mmio-socket-bridge.c'))
hw_virtmcu_modules += {'mmio-socket-bridge': mmio_bridge_ss}

# ── rust-dummy ──────────────────────────────────────────────────────────────────
# A QOM device where the boilerplate is in C but memory operations call into Rust.
# Demonstrates how to build mixed C/Rust peripherals without full QEMU Rust support.
rust_dummy_lib = custom_target(
  'rust_dummy_lib',
  input: 'rust-dummy/src/lib.rs',
  output: ['librust_dummy.a', 'rust_dummy_trigger.c'],
  command: ['sh', '-c', 'rustc --crate-type=staticlib -C panic=abort -O "$1" -o "$2" && echo "" > "$3"', 'sh', '@INPUT@', '@OUTPUT0@', '@OUTPUT1@']
)
rust_dummy_ss = ss.source_set()
rust_dummy_ss.add(files('rust-dummy/rust-dummy.c'))
rust_dummy_ss.add(rust_dummy_lib[1])
rust_dummy_ss.add(declare_dependency(
  link_args: [meson.current_build_dir() / 'librust_dummy.a']
))
hw_virtmcu_modules += {'rust-dummy': rust_dummy_ss}

# ── Add new devices above this line ──────────────────────────────────────────
modules += {'hw-virtmcu': hw_virtmcu_modules}
