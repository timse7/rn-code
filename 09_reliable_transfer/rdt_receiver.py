"""Receiver for the reliable-transfer example.

    python rdt_receiver.py [port] [gbn|sr]

Serves one transfer after another. Two receivers live here, and which one you
need depends on the sender:

    gbn   no buffer, cumulative acknowledgements -- for stop-and-wait and
          go-back-N (the default)
    sr    buffers early arrivals, acknowledges each packet -- for selective
          repeat

The receiver is as much part of a protocol as the sender: pair them wrongly
and the transfer will not work.

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
    KIND_SACK,
    LINGER,
    PORT,
    LossyChannel,
    pack,
    unpack,
)

HOST = ""
BUFSIZE = 4096


class Receiver:
    """Keeps no buffer and acknowledges cumulatively.

    Serves the stop-and-wait and go-back-N senders. Anything that does not
    arrive in order is thrown away, and the acknowledgement always names the
    next packet still wanted -- "I have everything below n". Throwing away
    perfectly good packets is what forces the sender to *go back*.
    """

    name = "no buffer, cumulative acknowledgements"

    def __init__(self, channel):
        self.channel = channel
        self.expected = 0  # the next sequence number we want
        self.delivered = 0  # packets handed to the application, in order
        self.discarded = 0  # duplicates and out-of-order arrivals

    def _reset(self):
        self.expected = 0
        self.delivered = 0
        self.discarded = 0

    def _on_data(self, seq):
        """Take one data packet; return the acknowledgement to send back."""
        if seq == self.expected:
            self.expected += 1  # in order: hand it to the application
            self.delivered += 1
        else:
            # Either a duplicate we already have, or a packet from beyond the
            # gap. With no buffer there is nowhere to put it.
            self.discarded += 1

        # Acknowledge in both cases. A duplicate usually means our earlier
        # acknowledgement was the thing that got lost.
        return pack(KIND_ACK, self.expected)

    def run_once(self, linger=LINGER):
        """Serve one transfer; return the number of packets the sender claims."""
        self._reset()
        self.channel.settimeout(None)  # wait indefinitely for the first packet

        while True:
            datagram, peer = self.channel.recvfrom(BUFSIZE)
            kind, number, _ = unpack(datagram)

            if kind == KIND_DATA:
                self.channel.sendto(self._on_data(number), peer)

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


class SelectiveRepeatReceiver(Receiver):
    """Buffers what arrives early and acknowledges each packet on its own.

    The two changes from the receiver above are the whole difference between
    go-back-N and selective repeat:

      * a packet that arrives before the gap ahead of it is kept, not thrown
        away, and handed over later once the gap is filled;
      * the acknowledgement names the packet that actually arrived, so the
        sender learns exactly which one is still missing and resends only
        that one.

    The price is the buffer, and the bookkeeping to go with it.
    """

    name = "buffers early arrivals, acknowledges each packet"

    def _reset(self):
        super()._reset()
        self.buffer = set()  # sequence numbers held back, waiting for a gap
        self.max_buffered = 0

    def _on_data(self, seq):
        if seq >= self.expected and seq not in self.buffer:
            self.buffer.add(seq)
            self.max_buffered = max(self.max_buffered, len(self.buffer))
        else:
            self.discarded += 1  # already delivered, or already held

        # Hand over as long a run as the buffer now allows.
        while self.expected in self.buffer:
            self.buffer.discard(self.expected)
            self.expected += 1
            self.delivered += 1

        # Acknowledge this packet, not a position in the stream.
        return pack(KIND_SACK, seq)


RECEIVERS = {"gbn": Receiver, "sr": SelectiveRepeatReceiver}


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    mode = sys.argv[2] if len(sys.argv) > 2 else "gbn"
    if mode not in RECEIVERS:
        sys.exit(f"usage: {sys.argv[0]} [port] [gbn|sr]")

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((HOST, port))
        channel = LossyChannel(sock)
        receiver = RECEIVERS[mode](channel)
        print(f"receiver listening on UDP port {port}", flush=True)
        print(f"mode: {receiver.name}", flush=True)

        try:
            while True:
                announced = receiver.run_once()
                print("--- transfer finished ---", flush=True)
                print(f"  announced by sender  {announced:>6} packets")
                print(f"  delivered in order   {receiver.delivered:>6} packets")
                print(f"  discarded            {receiver.discarded:>6} packets")
                if isinstance(receiver, SelectiveRepeatReceiver):
                    print(f"  most ever buffered   {receiver.max_buffered:>6} packets")
                print(
                    f"  acknowledgements dropped by the channel: {channel.dropped}",
                    flush=True,
                )
        except KeyboardInterrupt:
            print("\nreceiver stopped")


if __name__ == "__main__":
    main()
