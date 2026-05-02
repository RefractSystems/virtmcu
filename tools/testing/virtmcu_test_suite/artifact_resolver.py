"""
Finds the expected path for a built Rust binary across standard workspace locations.
It returns the path even if the file doesn't exist yet, prioritizing locations
where it actually exists if multiple are possible.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from tools.testing.env import WORKSPACE_DIR


def get_rust_binary_path(name: str) -> Path:
    """
    Finds the expected path for a built Rust binary across standard workspace locations.
    Prioritizes:
    1. CARGO_TARGET_DIR/release/<name> (if env var set)
    2. WORKSPACE_DIR/target/release/<name>
    3. tools/<name>/target/release/<name>
    4. System PATH (via shutil.which)
    5. Fallback candidate paths
    """

    # 1. Check CARGO_TARGET_DIR if set
    if "CARGO_TARGET_DIR" in os.environ:
        p = Path(os.environ["CARGO_TARGET_DIR"]) / f"release/{name}"
        if p.exists():
            return p

    # 2. Candidate paths within the workspace
    paths = [
        WORKSPACE_DIR / "target/release" / name,
        WORKSPACE_DIR / f"tools/{name}/target/release/{name}",
        # Some tools belong to specific workspaces like cyber_bridge
        WORKSPACE_DIR / f"tools/cyber_bridge/target/release/{name}",
        WORKSPACE_DIR / f"tools/zenoh_coordinator/target/release/{name}",
        WORKSPACE_DIR / f"tools/deterministic_coordinator/target/release/{name}",
    ]

    for p in paths:
        if p.exists():
            return p

    # 3. Check system PATH
    path_bin = shutil.which(name)
    if path_bin:
        return Path(path_bin)

    # 4. Fallback to standard target dir if it doesn't exist anywhere
    if "CARGO_TARGET_DIR" in os.environ:
        return Path(os.environ["CARGO_TARGET_DIR"]) / f"release/{name}"
    return WORKSPACE_DIR / "target/release" / name


def resolve_rust_binary(name: str) -> Path:
    """
    Finds a built Rust binary across standard workspace locations.
    Raises FileNotFoundError if it doesn't exist.
    """
    p = get_rust_binary_path(name)
    if not p.exists():
        raise FileNotFoundError(f"Binary {name} not found. Searched path: {p}. Did you run 'cargo build'?")
    return p
