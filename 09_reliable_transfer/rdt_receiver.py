"""Receiver for the reliable-transfer example.

    python rdt_receiver.py [port]

Serves one transfer after another. The same receiver works for both sender
protocols, because both use the same rule: acknowledge with the number of the
next packet still wanted. An acknowledgement is therefore cumulative -- "I
have everything below n" -- and a lost acknowledgement is harmless as long as
a later one gets through.

Stop it with Ctrl-C.
"""

import socket
import sys
import time

from rdt_common import (
    KIND_ACK,
    KIND_DATA,
    KIND_FIN,
    KIND_FINACK,
    LINGER,
    PORT,
    LossyChannel,
    pack,
    unpack,
)

HOST = ""
BUFSIZE = 4096


class Receiver:
    """Accepts packets in order and acknowledges what it has."""

    def __init__(self, channel):
        self.channel = channel
        self.expected = 0  # the next sequence number we want
        self.delivered = 0  # packets handed to the application, in order
        self.discarded = 0  # duplicates and out-of-order arrivals

    def run_once(self, linger=LINGER):
        """Serve one transfer; return the number of packets the sender claims."""
        self.expected = 0
        self.delivered = 0
        self.discarded = 0
        self.channel.settimeout(None)  # wait indefinitely for the first packet

        while True:
            datagram, peer = self.channel.recvfrom(BUFSIZE)
            kind, number, _ = unpack(datagram)

            if kind == KIND_DATA:
                if number == self.expected:
                    self.expected += 1  # in order: hand it to the application
                    self.delivered += 1
                else:
                    # Either a duplicate we already have, or a packet from
                    # beyond the gap. This receiver keeps no buffer, so it
                    # drops it and lets the sender resend -- that is exactly
                    # what makes go-back-N "go back".
                    self.discarded += 1

                # Acknowledge in both cases. A duplicate usually means our
                # earlier acknowledgement was the thing that got lost.
                self.channel.sendto(pack(KIND_ACK, self.expected), peer)

            elif kind == KIND_FIN:
                self.channel.sendto(pack(KIND_FINACK, self.expected), peer)
                self._linger(linger)
                return number

    def _linger(self, linger):
        """Stay a moment longer and answer repeated end-of-transfer packets.

        Our confirmation can be lost like anything else, and the sender will
        then ask again -- so somebody has to still be listening. Leaving
        immediately strands the sender, which is precisely why TCP holds a
        closed connection in TIME_WAIT instead of forgetting it at once.
        """
        deadline = time.monotonic() + linger
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return
            self.channel.settimeout(remaining)
            try:
                datagram, peer = self.channel.recvfrom(BUFSIZE)
            except socket.timeout:
                return
            kind, _, _ = unpack(datagram)
            if kind == KIND_FIN:
                self.channel.sendto(pack(KIND_FINACK, self.expected), peer)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((HOST, port))
        channel = LossyChannel(sock)
        receiver = Receiver(channel)
        print(f"receiver listening on UDP port {port}", flush=True)

        try:
            while True:
                announced = receiver.run_once()
                print("--- transfer finished ---", flush=True)
                print(f"  announced by sender  {announced:>6} packets")
                print(f"  delivered in order   {receiver.delivered:>6} packets")
                print(f"  discarded            {receiver.discarded:>6} packets")
                print(
                    f"  acknowledgements dropped by the channel: {channel.dropped}",
                    flush=True,
                )
        except KeyboardInterrupt:
            print("\nreceiver stopped")


if __name__ == "__main__":
    main()
