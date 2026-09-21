"""UDP sender that pushes small packets out as fast as it possibly can.

    python udp_flood_client.py [host] [port] [number of packets]

Sends fixed-size 1024-byte packets, each carrying a sequence number, and
finishes with a few end markers announcing how many packets were actually
handed to the network. Start udp_flood_server.py first; it counts what arrives
and reports the difference.

Nothing here waits for anything and nothing checks whether a packet arrived --
which is exactly what UDP does not do for you.
"""

import errno
import socket
import struct
import sys
import time

HOST = "localhost"
PORT = 9877
COUNT = 200_000  # packets per run
PAYLOAD = 1024  # bytes per packet, header included
END_REPEATS = 5  # end markers, because those can be lost too
SETTLE = 0.1  # seconds before the end markers, to let the receiver catch up

# Packet layout, identical in both programs. "!" means network byte order and
# no padding between the fields, so the header is exactly 9 bytes.
HEADER = struct.Struct("!BII")  # kind, sequence number, total
KIND_DATA = 0
KIND_END = 1
PADDING = b"x" * (PAYLOAD - HEADER.size)


def send_all(client_socket, dest, count):
    """Send `count` data packets; return how many the stack accepted."""
    sent = 0
    refused = 0
    # Local names: attribute lookups are not free in a loop this tight.
    pack = HEADER.pack
    sendto = client_socket.sendto

    start = time.perf_counter()
    for seq in range(count):
        try:
            sendto(pack(KIND_DATA, seq, 0) + PADDING, dest)
            sent += 1
        except OSError as exc:
            # The local stack refused to take the packet. This is *not* packet
            # loss: it never left the machine, so it must not be counted as
            # sent. It is also the only failure UDP ever reports.
            if exc.errno not in (errno.ENOBUFS, errno.EAGAIN, errno.EWOULDBLOCK):
                raise
            refused += 1
    elapsed = time.perf_counter() - start

    return sent, refused, elapsed


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else PORT
    count = int(sys.argv[3]) if len(sys.argv) > 3 else COUNT

    # Resolve the name once, here, and send to the numeric address afterwards.
    # Handing a hostname to sendto() makes the stack resolve it again for
    # every single packet, which costs far more time than the sending itself
    # and quietly turns this into a name-resolution benchmark.
    family, socktype, proto, _, dest = socket.getaddrinfo(
        host, port, socket.AF_INET, socket.SOCK_DGRAM
    )[0]

    with socket.socket(family, socktype, proto) as client_socket:
        # Do not wait for anybody. On a blocking socket the kernel makes the
        # sender wait whenever the receiver's queue is full, which throttles
        # this program to the receiver's pace -- and then nothing is ever
        # lost. "As fast as the client can" means not waiting.
        client_socket.setblocking(False)

        print(f"sending {count} packets of {PAYLOAD} bytes to {dest[0]}:{dest[1]}")
        sent, refused, elapsed = send_all(client_socket, dest, count)

        rate = sent / elapsed if elapsed else 0.0
        mbit = sent * PAYLOAD * 8 / elapsed / 1e6 if elapsed else 0.0
        print(f"handed to the network {sent} packets in {elapsed:.2f} s")
        print(f"  {rate:,.0f} packets/s = {mbit:.1f} Mbit/s")
        if refused:
            print(f"  {refused} packets the local stack refused (never sent)")

        # Announce the total. Sent several times, spaced out and on a blocking
        # socket, because this packet is as unreliable as all the others -- and
        # after a burst the receiver's queue is exactly where it is fullest.
        client_socket.setblocking(True)
        time.sleep(SETTLE)
        end = HEADER.pack(KIND_END, 0, sent) + PADDING
        for _ in range(END_REPEATS):
            client_socket.sendto(end, dest)
            time.sleep(0.02)

    print("done -- see the receiver for how many arrived")


if __name__ == "__main__":
    main()
