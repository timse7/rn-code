"""UDP receiver that counts packets and reports how many were lost.

    python udp_flood_server.py [port] [work per packet in us] [receive buffer]

Counterpart of udp_flood_client.py. Every data packet carries a sequence
number, so the receiver can see the gaps; at the end of a run the sender
announces how many packets it really put on the wire, and the difference is
the loss.

The second argument is how long the receiver pretends to work on each packet.
It defaults to a few microseconds, which is enough to make it slower than the
sender and so to produce visible loss. Pass 0 for a receiver that does nothing
but count -- over the loopback interface that will usually show no loss at
all, because there is no lossy link and no congested router in the way. Loss
happens when a queue overflows, and for that somebody has to be too slow.

Stop it with Ctrl-C.
"""

import socket
import struct
import sys
import time

HOST = ""  # all local interfaces
PORT = 9877
BUFSIZE = 2048  # big enough for one 1024-byte packet
WORK_US = 5.0  # simulated processing time per packet, microseconds
IDLE_TIMEOUT = 3.0  # wrap up a run if nothing arrives for this long

HEADER = struct.Struct("!BII")  # kind, sequence number, total
KIND_DATA = 0
KIND_END = 1


def burn(microseconds):
    """Busy-wait: sleep() is far too coarse for microsecond-scale work."""
    if microseconds <= 0:
        return
    deadline = time.perf_counter() + microseconds / 1e6
    while time.perf_counter() < deadline:
        pass


class Run:
    """Statistics of one measurement run."""

    def __init__(self):
        self.received = 0
        self.bytes = 0
        self.expected = 0  # next sequence number we would like to see
        self.gaps = 0  # packets skipped over: missing so far
        self.late = 0  # arrived after a higher number: reordered or duplicate
        self.first_seen = time.perf_counter()
        self.last_seen = self.first_seen

    def data(self, seq, size):
        self.received += 1
        self.bytes += size
        self.last_seen = time.perf_counter()

        # Gap detection with constant memory: no set of sequence numbers is
        # kept, only the number we expect to see next.
        if seq == self.expected:
            self.expected += 1
        elif seq > self.expected:
            self.gaps += seq - self.expected
            self.expected = seq + 1
        else:
            self.late += 1

    def report(self, sent):
        elapsed = max(self.last_seen - self.first_seen, 1e-9)
        mbit = self.bytes * 8 / elapsed / 1e6

        print("--- run finished ---")
        if sent is None:
            print("  the end marker never arrived, so the number of packets")
            print("  sent is unknown -- counting only what was received:")
            print(f"  received          {self.received:>10} packets")
            print(f"  gaps in sequence  {self.gaps:>10} packets")
        else:
            lost = sent - self.received
            percent = lost / sent * 100 if sent else 0.0
            print(f"  sent by client    {sent:>10} packets")
            print(f"  received          {self.received:>10} packets")
            print(f"  lost              {lost:>10} packets ({percent:.2f} %)")
            print(f"  gaps in sequence  {self.gaps:>10} packets")
        print(f"  reordered/dup     {self.late:>10} packets")
        print(
            f"  {self.bytes / 1e6:.1f} MB in {elapsed:.3f} s = {mbit:.1f} Mbit/s",
            flush=True,
        )


def serve(port, work_us, rcvbuf):
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
        if rcvbuf:
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, rcvbuf)
        # The kernel holds arriving datagrams in this buffer until the program
        # picks them up. Once it is full, every further datagram is dropped --
        # no error, no notification, nothing. That is where the loss happens.
        actual = server_socket.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)

        server_socket.bind((HOST, port))
        server_socket.settimeout(1.0)  # so an abandoned run can be wrapped up
        print(f"receiver listening on port {port}", flush=True)
        print(
            f"receive buffer: {actual} bytes, work per packet: {work_us} us", flush=True
        )

        run = None
        while True:
            try:
                data, _ = server_socket.recvfrom(BUFSIZE)
            except socket.timeout:
                # Even the end marker can be lost; do not wait for it forever.
                if run and time.perf_counter() - run.last_seen > IDLE_TIMEOUT:
                    run.report(None)
                    run = None
                continue

            if len(data) < HEADER.size:
                continue  # not one of ours
            kind, seq, total = HEADER.unpack_from(data)

            if kind == KIND_DATA:
                if run is None:
                    print("run started", flush=True)
                    run = Run()
                run.data(seq, len(data))
                burn(work_us)
            elif kind == KIND_END and run is not None:
                run.report(total)
                run = None  # ignore the repeated end markers that follow


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    work_us = float(sys.argv[2]) if len(sys.argv) > 2 else WORK_US
    rcvbuf = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    try:
        serve(port, work_us, rcvbuf)
    except KeyboardInterrupt:
        print("\nreceiver stopped")


if __name__ == "__main__":
    main()
