import asyncio
import os
from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_phase6_coordinator(zenoh_router, zenoh_coordinator, zenoh_session):  # noqa: ARG001
    """
    Phase 6 smoke test: Zenoh Multi-Node Coordinator.
    Migrated from test/phase6/smoke_test.sh
    """
    workspace_root = Path(Path(Path(__file__).parent.resolve().parent))

    env = os.environ.copy()
    env["ZENOH_ROUTER"] = zenoh_router

    # 1. Run comprehensive test suite
    proc = await asyncio.create_subprocess_exec(
        "python3",
        (Path(workspace_root) / "test/phase6/complete_test.py"),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout, stderr = await proc.communicate()
    assert proc.returncode == 0, f"complete_test.py failed:\nSTDOUT: {stdout.decode()}\nSTDERR: {stderr.decode()}"

    # 2. Run malformed packet survival test
    proc = await asyncio.create_subprocess_exec(
        "python3",
        (Path(workspace_root) / "test/phase6/repro_crash.py"),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout, stderr = await proc.communicate()
    assert proc.returncode == 0, f"repro_crash.py failed: {stderr.decode()}"

    # 3. Run stress test
    # Note: stress test might be slow
    proc = await asyncio.create_subprocess_exec(
        "python3",
        (Path(workspace_root) / "test/phase6/stress_test.py"),
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    stdout, stderr = await proc.communicate()
    assert proc.returncode == 0, f"stress_test.py failed: {stderr.decode()}"

    # Check if coordinator is still alive
    assert zenoh_coordinator.returncode is None
