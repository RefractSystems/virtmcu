"""
RISC-V boot test.
Verify that RISC-V firmware boots and prints "HI RV".
"""

from __future__ import annotations

import shutil
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from tools.testing.virtmcu_test_suite.simulation import Simulation


@pytest.mark.asyncio
async def test_riscv_boot(simulation: Simulation) -> None:

    from tools.testing.env import WORKSPACE_ROOT

    workspace_root = WORKSPACE_ROOT
    riscv_test_dir = workspace_root / "tests/fixtures/guest_apps/boot_riscv"
    dtb = riscv_test_dir / "minimal.dtb"
    kernel = riscv_test_dir / "hello.elf"

    if not dtb.exists() or not kernel.exists():
        import subprocess

        subprocess.run(
            [shutil.which("make") or "make", "-C", "tests/fixtures/guest_apps/boot_riscv"],
            check=True,
            cwd=workspace_root,
        )

    # Boot and check UART using Simulation
    simulation.add_node(
        node_id=0,
        dtb=dtb,
        kernel=kernel,
        extra_args=["-m", "512M", "--arch", "riscv64"],
        orchestrated=False,
    )
    async with simulation as sim:
        # In non-orchestrated mode, we don't use vta.step()
        assert sim.bridge is not None
        assert await sim.bridge.wait_for_line_on_uart("HI RV", timeout=10.0)
