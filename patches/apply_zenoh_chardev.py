#!/usr/bin/env python3
import sys
from pathlib import Path


def patch_file(filepath, marker, insertion, after=False):
    with Path(filepath).open() as f:
        content = f.read()
    if insertion in content:
        return False
    idx = content.find(marker)
    if idx == -1:
        print(f"Error: Could not find marker '{marker}' in {filepath}")
        sys.exit(1)
    if after:
        idx += len(marker)
    new_content = content[:idx] + insertion + content[idx:]
    with Path(filepath).open("w") as f:
        f.write(new_content)
    return True


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <qemu-source-dir>")
        sys.exit(1)

    qemu = Path(sys.argv[1]).resolve()
    char_c = Path(qemu) / "chardev" / "char.c"

    # 1. Patch qemu_chardev_opts in chardev/char.c
    marker4 = '.name = "size",'
    insertion4 = """        },{
            .name = "node",
            .type = QEMU_OPT_STRING,
        },{
            .name = "router",
            .type = QEMU_OPT_STRING,
        },{
            .name = "topic",
            .type = QEMU_OPT_STRING,"""
    if patch_file(char_c, marker4, insertion4, after=False):
        print(f"  patched {char_c}")


if __name__ == "__main__":
    main()
