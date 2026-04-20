import socket
import sys
from pathlib import Path

from tools.vproto import (
    SIZE_MMIO_REQ,
    SIZE_VIRTMCU_HANDSHAKE,
    VIRTMCU_PROTO_MAGIC,
    VIRTMCU_PROTO_VERSION,
    MmioReq,
    SyscMsg,
    VirtmcuHandshake,
)

SCRIPT_DIR = Path(Path(__file__).resolve().parent)
if SCRIPT_DIR not in sys.path:
    sys.path.append(str(SCRIPT_DIR))


def recvall(conn, n):
    data = b""
    while len(data) < n:
        chunk = conn.recv(n - len(data))
        if not chunk:
            return None
        data += chunk
    return data


def start_server(sock_path):
    if Path(sock_path).exists():
        Path(sock_path).unlink()

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    server.bind(sock_path)
    server.listen(1)
    print(f"Server listening on {sock_path}")

    conn, _ = server.accept()
    print("Connected")

    hs_data = recvall(conn, SIZE_VIRTMCU_HANDSHAKE)
    if not hs_data:
        print("Failed to receive handshake")
        return
    hs_in = VirtmcuHandshake.unpack(hs_data)
    if hs_in.magic != VIRTMCU_PROTO_MAGIC or hs_in.version != VIRTMCU_PROTO_VERSION:
        print(f"Handshake mismatch: {hs_in}")
        return

    hs_out = VirtmcuHandshake(magic=VIRTMCU_PROTO_MAGIC, version=VIRTMCU_PROTO_VERSION)
    conn.sendall(hs_out.pack())

    while True:
        data = recvall(conn, SIZE_MMIO_REQ)
        if not data:
            break

        req = MmioReq.unpack(data)
        print(
            f"REQ: type={req.type}, size={req.size}, vtime={req.vtime_ns}, addr=0x{req.addr:x}, data=0x{req.data:x}",
            flush=True,
        )

        # Send response
        resp = SyscMsg(type=0, irq_num=0, data=0)
        conn.sendall(resp.pack())
    conn.close()
    server.close()


if __name__ == "__main__":
    start_server("/tmp/mmio.sock")
