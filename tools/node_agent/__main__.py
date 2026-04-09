"""
tools/node_agent — DEPRECATED. Will be deleted in Phase 7.

This Python node agent is superseded by the native Zenoh QOM plugin (hw/zenoh/).
The "No Python in the Simulation Loop" mandate requires all clock sync and networking
to be implemented as native C/Rust QOM modules inside QEMU, not as external Python
processes. See PLAN.md Phase 7 and docs/ARCHITECTURE.md §7.

This file is kept temporarily as a reference for the wire protocol.
"""

import asyncio
import os
import sys

import zenoh

from .qemu_clock import QemuClockClient


ZENOH_ROUTER      = os.environ.get("ZENOH_ROUTER", "tcp/localhost:7447")
NODE_ID           = int(os.environ.get("NODE_ID", "0"))
CLOCK_SOCKET      = os.environ.get("QEMU_CLOCK_SOCKET", "/tmp/qemu-clock.sock")
CLOCK_MODE        = os.environ.get("CLOCK_MODE", "standalone")
# Clock modes:
#   standalone     — QEMU free-runs, no sync. Full TCG speed. (development)
#   slaved-suspend — NodeAgent does QMP stop/cont at quantum boundaries.
#                    ~95% of free-run speed. ±1 quantum jitter. (recommended)
#   slaved-icount  — libqemu qemu_icount_bias advance. Exact ns precision.
#                    ~15-20% of free-run speed. (only needed for sub-quantum timing)

ADVANCE_KEY       = f"sim/clock/advance/{NODE_ID}"
ETH_DELIVER_KEY   = f"sim/eth/frame/ta/{NODE_ID}"


async def run_slaved(session: zenoh.Session, clock: QemuClockClient) -> None:
    """
    Slaved mode: wait for TimeAuthority to send clock advance requests over Zenoh.
    QEMU advances exactly delta_ns per quantum — causally locked to MuJoCo physics.
    """
    print(f"[node_agent:{NODE_ID}] slaved mode — listening on {ADVANCE_KEY}")

    def on_advance(query: zenoh.Query) -> None:
        """Synchronous Zenoh queryable callback — runs in Zenoh's thread pool."""
        payload = bytes(query.payload) if query.payload else b""
        if len(payload) < 16:
            query.reply(ADVANCE_KEY, b"ERROR:bad payload")
            return

        import struct
        delta_ns, mujoco_time_ns = struct.unpack("<QQ", payload[:16])

        # Run the async advance in the event loop
        future = asyncio.run_coroutine_threadsafe(
            clock.advance(delta_ns, mujoco_time_ns),
            asyncio.get_event_loop(),
        )
        try:
            vtime_ns = future.result(timeout=10.0)
            reply_payload = struct.pack("<QI", vtime_ns, 0)
            query.reply(ADVANCE_KEY, reply_payload)
        except Exception as exc:
            query.reply(ADVANCE_KEY, f"ERROR:{exc}".encode())

    queryable = session.declare_queryable(ADVANCE_KEY, on_advance)
    print(f"[node_agent:{NODE_ID}] registered queryable — waiting for TimeAuthority")

    try:
        # Block until cancelled
        await asyncio.Event().wait()
    finally:
        queryable.undeclare()


async def run_standalone(clock: QemuClockClient) -> None:
    """
    Standalone mode: connect to QEMU socket but don't advance the clock.
    QEMU runs free at full speed (icount disabled). Used for development and CI.
    """
    print(f"[node_agent:{NODE_ID}] standalone mode — QEMU runs free (no clock stepping)")
    print(f"[node_agent:{NODE_ID}] connected to QEMU at {CLOCK_SOCKET}")
    # Just keep alive so the container stays running
    await asyncio.Event().wait()


async def main() -> None:
    print(f"[node_agent:{NODE_ID}] starting (mode={CLOCK_MODE})")

    # Connect to QEMU clock socket
    clock = QemuClockClient(CLOCK_SOCKET)
    print(f"[node_agent:{NODE_ID}] waiting for QEMU socket at {CLOCK_SOCKET} ...")

    if CLOCK_MODE == "slaved":
        await clock.connect(timeout=120.0)
        print(f"[node_agent:{NODE_ID}] QEMU connected")

        conf = zenoh.Config()
        conf.insert_json5("connect/endpoints", f'["{ZENOH_ROUTER}"]')
        session = zenoh.open(conf)

        try:
            await run_slaved(session, clock)
        finally:
            session.close()
            await clock.close()
    else:
        # Standalone: don't require clock socket — QEMU may not have -clocksock set
        await run_standalone(clock)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        sys.exit(0)
