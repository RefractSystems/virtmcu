from pathlib import Path

import pytest


@pytest.mark.asyncio
async def test_phase2_dynamic_plugin(qemu_launcher):
    """
    Phase 2 smoke test: Dynamic plugin loading.
    Verify that dummy-device is correctly registered in QOM.
    """
    workspace_root = Path(Path(Path(__file__).parent.resolve().parent))
    dtb = Path(workspace_root) / "test/phase1/minimal.dtb"

    # Note: dummy-device was replaced with rust-dummy in Phase 30
    bridge = await qemu_launcher(dtb, extra_args=["-device", "rust-dummy"])

    # Check QOM tree for the device
    res = await bridge.qmp.execute("qom-list", {"path": "/machine/peripheral-anon"})

    found = False
    for item in res:
        if item.get("type") == "child<rust-dummy>":
            found = True
            break

    assert found, f"rust-dummy not found in QOM tree: {res}"
