import os
import subprocess


def test_canfd_plugin_loads():
    env = os.environ.copy()

    # We must run it via run.sh to get module paths right
    cmd = [
        "bash",
        "scripts/run.sh",
        "--dtb",
        "test/phase1/minimal.dtb",
        "-object",
        "can-bus,id=canbus0",
        "-object",
        "can-host-zenoh,id=canhost0,canbus=canbus0,node=test_node,router=,topic=sim/can",
        "-monitor",
        "none",
        "-serial",
        "none",
        "-nographic",
        "-display",
        "none",
        "-S",
    ]

    p = subprocess.Popen(cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        p.wait(timeout=2.0)
    except subprocess.TimeoutExpired:
        p.kill()
        assert True
    else:
        out, err = p.communicate()
        print(f"STDOUT: {out.decode()}")
        print(f"STDERR: {err.decode()}")
        assert p.returncode == 0, f"QEMU crashed or failed to load the plugin. STDERR: {err.decode()}"
