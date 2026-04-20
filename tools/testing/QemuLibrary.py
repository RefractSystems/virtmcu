import asyncio
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Ensure workspace root is in sys.path for Robot Framework environments
workspace_root = Path(__file__).resolve().parent / "../../"
if str(workspace_root) not in sys.path:
    sys.path.insert(0, str(workspace_root))

from tools.testing.qmp_bridge import QmpBridge  # noqa: E402


class QemuLibrary:
    """
    Robot Framework library for controlling QEMU via QMP.
    Provides a synchronous interface to the asynchronous QmpBridge.
    """

    ROBOT_LIBRARY_SCOPE = "GLOBAL"

    def __init__(self):
        self.bridge = QmpBridge()
        # Robot Framework is synchronous; create a dedicated event loop for the session.
        # Never use get_event_loop() here — it is deprecated in Python 3.10+ when no
        # running loop exists, and raises RuntimeError in 3.12.
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.proc: subprocess.Popen | None = None
        self.tmpdir: str | None = None

    def _run(self, coro):
        if self.loop.is_closed():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
        return self.loop.run_until_complete(coro)

    def launch_qemu(
        self, dtb_path: str, kernel_path: str | None = None, extra_args: str | list[str] | None = None
    ) -> tuple[str, str]:
        """
        Launches QEMU using the run.sh script and returns the QMP and UART socket paths.
        """
        tmpdir = tempfile.mkdtemp(prefix="virtmcu-robot-")
        qmp_sock = Path(tmpdir) / "qmp.sock"
        uart_sock = Path(tmpdir) / "uart.sock"

        workspace_root = Path.cwd()
        run_script = workspace_root / "scripts/run.sh"

        cmd = [str(run_script), "--dtb", str(Path(dtb_path).resolve())]
        if kernel_path:
            cmd.extend(["--kernel", str(Path(kernel_path).resolve())])

        cmd.extend(
            [
                "-qmp",
                f"unix:{qmp_sock},server,nowait",
                "-serial",
                f"unix:{uart_sock},server,nowait",
                "-display",
                "none",
                "-nographic",
            ]
        )

        if extra_args:
            if isinstance(extra_args, str):
                cmd.extend(extra_args.split())
            else:
                cmd.extend(extra_args)

        self.proc = subprocess.Popen(
            [str(arg) for arg in cmd],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=os.environ.copy(),
            start_new_session=True,  # Replace preexec_fn=os.setsid
        )
        self.tmpdir = tmpdir

        # Wait for sockets
        for _ in range(100):
            if self.proc.poll() is not None:
                stdout, stderr = self.proc.communicate()
                raise RuntimeError(
                    f"QEMU exited unexpectedly (rc={self.proc.returncode}) before sockets appeared.\n"
                    f"STDOUT: {stdout.decode()}\nSTDERR: {stderr.decode()}"
                )
            if Path(qmp_sock).exists() and Path(uart_sock).exists():
                break
            time.sleep(0.1)
        else:
            self.proc.terminate()
            stdout, stderr = self.proc.communicate()
            raise RuntimeError(
                f"QEMU sockets did not appear in time. STDOUT: {stdout.decode()} STDERR: {stderr.decode()}"
            )

        return str(qmp_sock), str(uart_sock)

    def connect_to_qemu(self, qmp_socket_path: str, uart_socket_path: str | None = None):
        """
        Connects to the QEMU QMP and UART sockets.
        """
        self._run(self.bridge.connect(qmp_socket_path, uart_socket_path))

    def start_emulation(self):
        """
        Starts or resumes the emulation.
        """
        self._run(self.bridge.start_emulation())

    def pause_emulation(self):
        """
        Pauses the emulation.
        """
        self._run(self.bridge.pause_emulation())

    def reset_emulation(self):
        """
        Resets the emulation.
        """
        self._run(self.bridge.execute("system_reset"))

    def wait_for_line_on_uart(self, pattern: str, timeout: float | str = 10.0):
        """
        Waits for a specific pattern to appear on the UART.
        """
        found = self._run(self.bridge.wait_for_line_on_uart(pattern, float(timeout)))
        if not found:
            raise AssertionError(
                f"Pattern '{pattern}' not found on UART within {timeout}s. Current buffer: {self.bridge.uart_buffer!r}"
            )

    def write_to_uart(self, text: str):
        """
        Writes text to the UART socket.
        """
        self._run(self.bridge.write_to_uart(text))

    def pc_should_be_equal(self, expected_pc: int | str):
        """
        Asserts that the current Program Counter is equal to the expected value.
        """
        actual_pc = self._run(self.bridge.get_pc())
        expected = int(expected_pc, 0) if isinstance(expected_pc, str) else expected_pc
        if actual_pc != expected:
            raise AssertionError(f"PC expected to be {hex(expected)}, but was {hex(actual_pc)}")

    def execute_monitor_command(self, command: str) -> str:
        """
        Executes a Human Monitor Command (HMP) and returns the output.
        """
        return self._run(self.bridge.execute("human-monitor-command", {"command-line": command}))

    def close_all_connections(self):
        """
        Closes all QMP and UART connections and cleans up the QEMU process.
        """
        self._run(self.bridge.close())
        if self.proc:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
                self.proc.wait(timeout=5)
            except Exception:
                if self.proc:
                    self.proc.kill()
            self.proc = None

        if self.tmpdir:
            shutil.rmtree(self.tmpdir, ignore_errors=True)
            self.tmpdir = None

        if self.loop.is_running():
            # Should not be running if _run finished
            pass
        self.loop.close()
