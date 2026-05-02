"""
SOTA single-entry-point simulation harness.

Subsumes legacy single-node and multi-node orchestrators
under one class with a strict, framework-owned lifecycle.

Lifecycle (see /workspace/docs/guide/03-testing-strategy.md §6):
  1. Spawn all QEMU nodes frozen (`-S` injected by qemu_launcher).
  2. Liveliness barrier (`vta.init()` waits for `sim/clock/liveliness/{nid}`)
     and 0-ns sync — performed while QEMU is still frozen.
  3. Router barrier (`ensure_session_routing(session)`).
  4. `cont` (start_emulation) issued to all nodes.
  5. Strict reverse-order teardown.

Use via the `simulation` pytest fixture defined in `conftest_core.py`.
Direct instantiation in tests is banned (see CLAUDE.md §SOTA).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tools.testing.utils import get_time_multiplier
from tools.testing.virtmcu_test_suite.conftest_core import (
    VirtualTimeAuthority,
    ensure_session_routing,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine
    from pathlib import Path

    import zenoh

    from tools.testing.qmp_bridge import QmpBridge
    from tools.testing.virtmcu_test_suite.transport import SimulationTransport

logger = logging.getLogger(__name__)


@dataclass
class _NodeSpec:
    node_id: int
    dtb: str | Path
    kernel: str | Path | None
    extra_args: list[str] = field(default_factory=list)
    orchestrated: bool = True


class Simulation:
    """
    Single SOTA entry point for all firmware-executing simulations.

    Use the `simulation` pytest fixture; do not instantiate directly.
    """

    def __init__(
        self,
        *,
        zenoh_session: zenoh.Session,
        zenoh_router: str,
        qemu_launcher: Callable[..., Coroutine[Any, Any, QmpBridge]],
        init_barrier: bool = True,
    ) -> None:
        self._session = zenoh_session
        self._router = zenoh_router
        self._launcher = qemu_launcher
        self._specs: list[_NodeSpec] = []
        self._bridges: list[QmpBridge] = []
        self._vta: VirtualTimeAuthority | None = None
        # When False, __aenter__ skips vta.init() and ensure_session_routing,
        # so the test can drive boot grace-period scenarios. The framework
        # still injects -S and `cont` is still issued at the end. Default True.
        self._init_barrier = init_barrier
        # Optional transport (zenoh / unix / fault-injecting). When set, the VTA
        # is built by the transport so per-transport semantics are honored.
        self.transport: SimulationTransport | None = None

    def add_node(
        self,
        *,
        node_id: int,
        dtb: str | Path,
        kernel: str | Path | None = None,
        extra_args: list[str] | None = None,
        orchestrated: bool = True,
    ) -> None:
        if self._bridges:
            raise RuntimeError(
                "Simulation.add_node() must be called before entering the async context"
            )
        self._specs.append(_NodeSpec(node_id, dtb, kernel, list(extra_args or []), orchestrated))

    @property
    def vta(self) -> VirtualTimeAuthority:
        if self._vta is None:
            raise RuntimeError(
                "Simulation.vta is only available after entering the async context"
            )
        return self._vta

    @property
    def bridge(self) -> QmpBridge:
        if len(self._bridges) != 1:
            raise RuntimeError(
                f"Simulation.bridge is only valid for single-node sims (have {len(self._bridges)})"
            )
        return self._bridges[0]

    @property
    def bridges(self) -> list[QmpBridge]:
        return list(self._bridges)

    def bridge_for(self, node_id: int) -> QmpBridge:
        """Return the bridge for a specific node_id (registered via `add_node`)."""
        for spec, bridge in zip(self._specs, self._bridges, strict=True):
            if spec.node_id == node_id:
                return bridge
        raise KeyError(f"Simulation has no bridge for node_id={node_id}")

    def uart_buffer(self, node_id: int) -> str:
        """Convenience accessor for guest UART output by node_id."""
        return self.bridge_for(node_id).uart_buffer

    async def __aenter__(self) -> Simulation:
        if not self._specs:
            raise RuntimeError(
                "Simulation has no nodes — call add_node() before entering the context"
            )

        prepared = [self._inject_determinism_args(spec) for spec in self._specs]
        spawn_tasks = [
            self._launcher(
                dtb_path=spec.dtb,
                kernel_path=spec.kernel,
                extra_args=args,
                ignore_clock_check=True,
            )
            for spec, args in zip(self._specs, prepared, strict=True)
        ]
        self._bridges = await asyncio.gather(*spawn_tasks)

        node_ids = [s.node_id for s in self._specs if s.orchestrated]
        if self.transport is not None:
            self._vta = self.transport.get_vta(node_ids)  # type: ignore[assignment]
        else:
            self._vta = VirtualTimeAuthority(self._session, node_ids)
        assert self._vta is not None

        if self._init_barrier:
            await self._vta.init()
            await ensure_session_routing(self._session)

        for bridge in self._bridges:
            await bridge.start_emulation()

        return self

    async def __aexit__(self, *exc: object) -> None:
        for bridge in reversed(self._bridges):
            await bridge.close()

    async def run_until(
        self,
        condition: Callable[[], bool],
        *,
        timeout: float = 5.0,
        step_ns: int = 1_000_000,
    ) -> None:
        """
        Advance virtual time in steps of `step_ns` until `condition()` is True
        or `timeout` wall-clock seconds elapse. Mirrors the existing
        `SimulationOrchestrator.run_until` API for migration parity.
        """
        if self._vta is None:
            raise RuntimeError("run_until() called before Simulation context entered")

        start = time.monotonic()
        while time.monotonic() - start < timeout:
            if condition():
                return
            await self._vta.step(step_ns)
        if not condition():
            raise TimeoutError(
                f"Simulation.run_until: condition not met within {timeout}s"
            )

    def _inject_determinism_args(self, spec: _NodeSpec) -> list[str]:
        """
        Inject standard determinism args into a node's extra_args:
          - `router=`, `node=`, `mode=slaved-icount`, `stall-timeout=` on `virtmcu-clock`
          - `router=` on other `virtmcu` devices/chardevs
          - default `virtmcu-clock` device if none supplied
          - `-icount shift=0,align=off,sleep=off` whenever slaved-icount is in use

        Idempotent: leaves explicitly-supplied flags alone. Mirrors the legacy
        `simulation` fixture's `_create_sim` arg processing so the new lifecycle
        is a drop-in replacement.
        """
        args_in = list(spec.extra_args)
        node_id = spec.node_id
        router = self._router

        base_stall = int(os.environ.get("VIRTMCU_STALL_TIMEOUT_MS", "5000"))
        scaled_stall = int(base_stall * get_time_multiplier())

        processed: list[str] = []
        has_clock = False

        i = 0
        while i < len(args_in):
            arg = str(args_in[i])
            if arg in ["-device", "-chardev", "-netdev"] and i + 1 < len(args_in):
                val = str(args_in[i + 1])
                if "virtmcu-clock" in val:
                    has_clock = True
                    if "router=" not in val:
                        val = f"{val},router={router}"
                    if "node=" not in val:
                        val = f"{val},node={node_id}"
                    if "mode=" not in val:
                        val = f"{val},mode=slaved-icount"
                    if "stall-timeout=" not in val:
                        val = f"{val},stall-timeout={scaled_stall}"
                elif "virtmcu" in val:
                    if "router=" not in val:
                        val = f"{val},router={router}"
                    if "node=" not in val:
                        val = f"{val},node={node_id}"
                processed.extend([arg, val])
                i += 2
                continue

            if "virtmcu-clock" in arg:
                has_clock = True
                if "router=" not in arg:
                    arg = f"{arg},router={router}"
                if "node=" not in arg:
                    arg = f"{arg},node={node_id}"
                if "mode=" not in arg:
                    arg = f"{arg},mode=slaved-icount"
                if "stall-timeout=" not in arg:
                    arg = f"{arg},stall-timeout={scaled_stall}"
                processed.extend(["-device", arg])
            elif "virtmcu" in arg and arg not in ["-device", "-chardev", "-global"]:
                if i > 0 and args_in[i - 1] == "-global":
                    processed.append(arg)
                else:
                    if "router=" not in arg:
                        arg = f"{arg},router={router}"
                    if "node=" not in arg:
                        arg = f"{arg},node={node_id}"
                    prefix = "-chardev" if "id=" in arg else "-device"
                    processed.extend([prefix, arg])
            else:
                processed.append(arg)
            i += 1

        if not has_clock and spec.orchestrated:
            processed.extend(
                [
                    "-device",
                    (
                        f"virtmcu-clock,node={node_id},router={router},"
                        f"stall-timeout={scaled_stall},mode=slaved-icount"
                    ),
                ]
            )
        if any("slaved-icount" in a for a in processed) and "-icount" not in processed:
            processed.extend(["-icount", "shift=0,align=off,sleep=off"])
        if "-S" not in processed:
            processed.append("-S")
        return processed
