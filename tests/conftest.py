import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import pytest_asyncio
import zenoh

from tools.testing.qmp_bridge import QmpBridge
from tools.vproto import ClockAdvanceReq, ClockReadyResp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TimeAuthority:
    """
    Helper to drive QEMU virtual clock via Zenoh.
    """

    def __init__(self, session, node_id=0):
        self.session = session
        self.topic = f"sim/clock/advance/{node_id}"
        self.current_vtime_ns = 0

    async def step(self, delta_ns, timeout=10.0, delay=0):
        target_vtime = self.current_vtime_ns + delta_ns
        req = ClockAdvanceReq(delta_ns=delta_ns, mujoco_time_ns=0)
        logger.info(f"TimeAuthority: stepping {delta_ns}ns (target={target_vtime}) on {self.topic}")

        if delay > 0:
            await asyncio.sleep(delay)

        # zenoh-python get() is blocking, but we want async.
        replies = await asyncio.to_thread(
            lambda: list(self.session.get(self.topic, payload=req.pack(), timeout=timeout))
        )

        if not replies:
            logger.error(f"TimeAuthority: NO REPLIES from {self.topic}")
            raise TimeoutError(f"TimeAuthority: no reply from {self.topic}")

        reply = replies[0]
        if reply.ok:
            resp = ClockReadyResp.unpack(reply.ok.payload.to_bytes())
            logger.info(
                f"TimeAuthority: received reply: current_vtime={resp.current_vtime_ns}, error={resp.error_code}"
            )
            if resp.error_code != 0:
                logger.warning(f"TimeAuthority: error_code={resp.error_code}")
                # For stall tests, return the error code if it's not OK
                return resp.error_code

            # Update current vtime with actual time reached by QEMU
            self.current_vtime_ns = resp.current_vtime_ns
            return self.current_vtime_ns
        logger.error(f"TimeAuthority: ERROR REPLY from {self.topic}: {reply.err}")
        raise RuntimeError(f"TimeAuthority: error reply: {reply.err}")

    async def step_vtime(self, delta_ns, timeout=10.0, delay=0):
        """Same as step but returns the vtime returned by QEMU."""
        return await self.step(delta_ns, timeout, delay)


@pytest_asyncio.fixture
async def zenoh_session(zenoh_router):
    config = zenoh.Config()
    config.insert_json5("connect/endpoints", f'["{zenoh_router}"]')
    config.insert_json5("scouting/multicast/enabled", "false")
    session = await asyncio.to_thread(lambda: zenoh.open(config))
    yield session
    await asyncio.to_thread(session.close)


@pytest_asyncio.fixture
async def time_authority(zenoh_session):
    return TimeAuthority(zenoh_session)


@pytest_asyncio.fixture
async def zenoh_router(worker_id):  # noqa: ARG001
    """
    Fixture that starts a persistent Zenoh router for the duration of the test.
    Supports pytest-xdist parallelization by dynamically binding to a free port.
    """
    import socket

    tests_dir = Path(Path(__file__).resolve().parent)
    router_script = Path(tests_dir) / "zenoh_router_persistent.py"

    # Find a dynamically free port
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = s.getsockname()[1]
    s.close()

    endpoint = f"tcp/127.0.0.1:{port}"

    logger.info(f"Starting Zenoh Router on {endpoint}...")

    # We MUST NOT run global cleanup like 'make clean-sim' here as it would kill other parallel tests!

    proc = await asyncio.create_subprocess_exec(
        "python3", "-u", router_script, endpoint, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )

    # Wait for router to be ready
    await asyncio.sleep(1.0)

    yield endpoint

    if proc.returncode is None:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=2.0)
        except TimeoutError:
            proc.kill()
            await proc.wait()


@pytest_asyncio.fixture
async def zenoh_coordinator(zenoh_router):
    """
    Fixture that starts the zenoh_coordinator.
    """
    curr = Path(Path(__file__).resolve().parent)
    while str(curr) != "/" and not (curr / "tools").exists():
        curr = Path(curr).parent
    workspace_root = curr
    coord_bin = Path(workspace_root) / "tools/zenoh_coordinator/target/release/zenoh_coordinator"

    if not Path(coord_bin).exists():
        # Fallback to debug if release doesn't exist
        coord_bin = Path(workspace_root) / "tools/zenoh_coordinator/target/debug/zenoh_coordinator"

    if not Path(coord_bin).exists():
        # Try to build it
        logger.info("Building zenoh_coordinator...")
        proc = await asyncio.create_subprocess_exec(
            "cargo", "build", "--release", cwd=(Path(workspace_root) / "tools/zenoh_coordinator")
        )
        await proc.wait()
        coord_bin = Path(workspace_root) / "tools/zenoh_coordinator/target/release/zenoh_coordinator"

    logger.info(f"Starting Zenoh Coordinator connecting to {zenoh_router}...")

    cmd = [coord_bin, "--connect", zenoh_router]

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=None,  # Inherit from parent (pytest -s will show it)
        stderr=None,
        env=os.environ.copy(),
    )

    await asyncio.sleep(1.0)

    yield proc

    if proc.returncode is None:
        proc.terminate()
        try:
            await asyncio.wait_for(proc.wait(), timeout=2.0)
        except TimeoutError:
            proc.kill()
            await proc.wait()


@pytest_asyncio.fixture
async def qemu_launcher():
    """
    Fixture that returns a function to launch QEMU instances.
    Ensures all instances are cleaned up after the test.
    """
    instances: list[dict[str, Any]] = []

    async def _launch(dtb_path, kernel_path=None, extra_args=None, ignore_clock_check=False):
        # Create a unique temporary directory for this QEMU instance
        tmpdir = tempfile.mkdtemp(prefix="virtmcu-test-")
        qmp_sock = Path(tmpdir) / "qmp.sock"
        uart_sock = Path(tmpdir) / "uart.sock"

        # Build the command using run.sh
        # We use absolute paths to ensure it works from any directory
        curr = Path(Path(__file__).resolve().parent)
        while str(curr) != "/" and not (curr / "scripts").exists():
            curr = Path(curr).parent
        workspace_root = curr
        run_script = Path(workspace_root) / "scripts/run.sh"

        cmd: list[str] = [str(run_script), "--dtb", str(Path(dtb_path).resolve())]
        if kernel_path:
            cmd.extend(["--kernel", str(Path(kernel_path).resolve())])

        # Add QMP and UART sockets
        # Note: we use 'server,nowait' because QEMU should start and wait for us
        cmd.extend(
            [
                "-qmp",
                f"unix:{qmp_sock},server,nowait",
                "-display",
                "none",
                "-nographic",
            ]
        )

        # Only add default serial if not overridden in extra_args
        has_serial = False
        if extra_args:
            for arg in extra_args:
                if arg in ["-serial", "-chardev"]:
                    has_serial = True
                    break

        if not has_serial:
            cmd.extend(["-serial", f"unix:{uart_sock},server,nowait"])

        if extra_args:
            cmd.extend(extra_args)

        # Task 4.1b: Critical isolation constraint - standalone mode only
        if not ignore_clock_check:
            for arg in cmd:
                if "zenoh-clock" in str(arg):
                    raise ValueError(
                        "zenoh-clock device detected in standalone test suite. "
                        "Phase 4 tests must run without external clock plugins."
                    )

        logger.info(f"Launching QEMU: {' '.join(cmd)}")

        # Start the process
        proc = await asyncio.create_subprocess_exec(
            *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, env=os.environ.copy()
        )

        # Wait for sockets to be created by QEMU.
        # Poll every 100 ms (up to 10 s). Also check for premature exit.
        retries = 100
        while retries > 0:
            if proc.returncode is not None:
                # QEMU exited before sockets appeared — capture output and fail fast.
                stdout, stderr = await proc.communicate()
                raise RuntimeError(
                    f"QEMU exited unexpectedly (rc={proc.returncode}) before sockets appeared.\n"
                    f"STDOUT: {stdout.decode()}\nSTDERR: {stderr.decode()}"
                )
            if Path(qmp_sock).exists() and (has_serial or Path(uart_sock).exists()):
                break
            await asyncio.sleep(0.1)
            retries -= 1
        else:
            # 10 s elapsed — kill the process and drain its output.
            proc.terminate()
            stdout, stderr = await proc.communicate()
            logger.error(f"QEMU failed to start. STDOUT: {stdout.decode()} STDERR: {stderr.decode()}")
            raise TimeoutError("QEMU QMP/UART sockets did not appear in time")

        bridge = QmpBridge()
        await bridge.connect(str(qmp_sock), None if has_serial else str(uart_sock))

        instance = {"proc": proc, "bridge": bridge, "tmpdir": tmpdir}
        instances.append(instance)
        return bridge

    yield _launch

    # Cleanup
    for inst in instances:
        try:
            await inst["bridge"].close()
        except Exception as e:
            logger.warning(f"Error closing bridge: {e}")

        proc = inst["proc"]
        if proc.returncode is None:
            proc.terminate()
            try:
                await asyncio.wait_for(proc.wait(), timeout=5.0)
            except TimeoutError:
                proc.kill()
                await proc.wait()

        shutil.rmtree(inst["tmpdir"], ignore_errors=True)


@pytest_asyncio.fixture
async def qmp_bridge(qemu_launcher):
    """
    A convenience fixture that launches a default QEMU instance with
    the phase1 minimal DTB and hello.elf firmware.

    Uses -S to start paused, connects, and then resumes to ensure
    that early firmware output is captured.
    """
    dtb = "test/phase1/minimal.dtb"
    kernel = "test/phase1/hello.elf"

    # Ensure DTB exists
    if not Path(dtb).exists():
        # Try to build it if missing
        subprocess.run(["make", "-C", "test/phase1", "minimal.dtb"], check=True)

    bridge = await qemu_launcher(dtb, kernel, extra_args=["-S"])
    await bridge.start_emulation()
    return bridge
