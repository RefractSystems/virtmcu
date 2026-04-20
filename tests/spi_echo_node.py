import struct
import sys
import time

import zenoh


def main():
    if len(sys.argv) < 2:
        print("Usage: spi_echo_node.py <router_endpoint>")
        sys.exit(1)

    router = sys.argv[1]
    config = zenoh.Config()
    config.insert_json5("connect/endpoints", f'["{router}"]')
    config.insert_json5("scouting/multicast/enabled", "false")

    print(f"Connecting to Zenoh on {router}...")
    session = zenoh.open(config)

    topic = "sim/spi/spi0/0"

    def on_query(query):
        payload = query.payload.to_bytes()
        if len(payload) >= 16 + 4:
            # Header is 16 bytes, data is 4 bytes
            data = payload[16:20]
            val = struct.unpack("<I", data)[0]
            print(f"Received SPI transfer: 0x{val:08x}")
            # Echo back
            query.reply(zenoh.Sample(topic, data))  # type: ignore[call-arg]

    print(f"Declaring queryable on {topic}...")
    _ = session.declare_queryable(topic, on_query)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        session.close()


if __name__ == "__main__":
    main()
