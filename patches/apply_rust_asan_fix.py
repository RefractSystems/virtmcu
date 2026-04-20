#!/usr/bin/env python3
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("Usage: apply_rust_asan_fix.py <qemu_dir>")
        sys.exit(1)

    qemu_dir = Path(sys.argv[1])
    meson_build = qemu_dir / "meson.build"

    if not meson_build.exists():
        print(f"Error: {meson_build} not found")
        sys.exit(1)

    content = meson_build.read_text()

    changed = False

    # 1. Patch AddressSanitizer (asan)
    if "add_project_arguments('-C', 'link-arg=-fsanitize=address', language: 'rust')" not in content:
        target = "qemu_ldflags = ['-fsanitize=address'] + qemu_ldflags"
        if target in content:
            print("  -> Adding ASan flags for Rust...")
            insertion = "\n    if have_rust\n      add_project_arguments('-C', 'link-arg=-fsanitize=address', language: 'rust')\n    endif"
            content = content.replace(target, target + insertion)
            changed = True

    # 2. Patch UndefinedBehaviorSanitizer (ubsan)
    if "add_project_arguments('-C', 'link-arg=-fsanitize=undefined', language: 'rust')" not in content:
        target_ubsan = "qemu_ldflags += ['-fsanitize=undefined']"
        if target_ubsan in content:
            print("  -> Adding UBSan flags for Rust...")
            insertion_ubsan = "\n    if have_rust\n      add_project_arguments('-C', 'link-arg=-fsanitize=undefined', language: 'rust')\n    endif"
            content = content.replace(target_ubsan, target_ubsan + insertion_ubsan)
            changed = True

    if changed:
        meson_build.write_text(content)
        print("✓ Patched meson.build for Rust ASan/UBSan support")
    else:
        print("  -> Rust ASan/UBSan support already present or targets not found in meson.build")


if __name__ == "__main__":
    main()
