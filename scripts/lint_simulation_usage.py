#!/usr/bin/env python3
"""
AST-based lint for enforcing VirtMCU simulation framework usage.
Banned: manual ensure_session_routing, manual qemu_launcher,
and manual -S in extra_args.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path


def lint_file(path: Path) -> list[str]:
    violations = []
    try:
        with path.open("r", encoding="utf-8") as f:
            content = f.read()
            lines = content.splitlines()
            tree = ast.parse(content, filename=str(path))
    except (OSError, SyntaxError, ValueError) as e:
        return [f"{path}:0: Error parsing file: {e}"]

    for node in ast.walk(tree):
        # Rule 1, 2, 3: Banned function/class calls
        if isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr

            if name == "ensure_session_routing":
                # Exception: framework code or explicitly whitelisted with a comment
                is_exception = path.name in ("conftest_core.py", "simulation.py")
                if not is_exception:
                    # Symmetric check: 3 lines back, current line, 1 line forward
                    for i in range(max(0, node.lineno - 3), min(len(lines), node.lineno + 1)):
                        if "ENSURE_ROUTING_EXCEPTION" in lines[i]:
                            is_exception = True
                            break
                if not is_exception:
                    violations.append(
                        f"{path}:{node.lineno}: Banned call to ensure_session_routing(). "
                        "The Simulation framework handles this automatically."
                    )

            if name == "qemu_launcher":
                # Exception: conftest_core.py contains the only approved callers
                # (qmp_bridge, simulation fixture, and inspection_bridge).
                is_exception = path.name == "conftest_core.py"
                if not is_exception:
                    violations.append(
                        f"{path}:{node.lineno}: Banned call to qemu_launcher(). "
                        "Use simulation or inspection_bridge instead."
                    )

            if name in ("Simulation", "VirtmcuSimulation", "SimulationOrchestrator"):
                # Exception: conftest_core.py (fixture) or simulation.py (implementation).
                # `SimulationOrchestrator` was deleted but is kept here as a
                # tripwire — if a future change re-introduces it, the lint fires.
                is_exception = path.name in ("conftest_core.py", "simulation.py")
                if not is_exception:
                    violations.append(
                        f"{path}:{node.lineno}: Banned direct {name}() instantiation. "
                        "Use the simulation fixture instead."
                    )

        # Rule 4: Manual -S in extra_args
        if isinstance(node, ast.keyword) and node.arg == "extra_args":
            if isinstance(node.value, ast.List):
                for elt in node.value.elts:
                    if isinstance(elt, ast.Constant) and elt.value == "-S":
                        # Exception: internal framework code or QemuLibrary tests
                        is_exception = path.name in (
                            "conftest_core.py",
                            "simulation.py",
                            "test_device_realization.py",
                            "test_qemu_library_pytest.py",
                        )
                        if not is_exception:
                            violations.append(
                                f"{path}:{node.lineno}: Banned manual '-S' in extra_args. "
                                "The framework (Simulation or inspection_bridge) handles this."
                            )

    return violations


def main() -> None:
    root = Path("/workspace")
    tests_dir = root / "tests"
    tools_testing_dir = root / "tools/testing"

    all_violations = []

    for path in sorted(list(tests_dir.rglob("*.py")) + list(tools_testing_dir.rglob("*.py"))):
        if "fixtures" in path.parts or "__pycache__" in path.parts:
            continue
        all_violations.extend(lint_file(path))

    if all_violations:
        for v in all_violations:
            print(v)
        sys.exit(1)
    else:
        print("Simulation usage lint passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
