"""Sender for the reliable-transfer example, in two flavours.

    python rdt_sender.py [host] [port] [sw|gbn] [packets]

    sw    stop-and-wait: send one packet, wait for its acknowledgement
    gbn   go-back-N: keep a window of unacknowledged packets in flight

Both sit on a plain UDP socket and both survive a lossy channel. The
difference is only how many packets may be outstanding at once, and that
difference is what the transfer time shows.
"""

import socket
import sys
import time

from rdt_common import (
    COUNT,
    KIND_ACK,
    KIND_DATA,
    KIND_FIN,
    KIND_FINACK,
    MAX_RETRIES,
    PAYLOAD,
    PORT,
    RTO,
    WINDOW,
    LossyChannel,
    pack,
    unpack,
)

BUFSIZE = 4096


class Result:
    """What one transfer cost."""

    def __init__(self, name):
        self.name = name
        self.packets = 0  # data packets handed to the channel
        self.retransmitted = 0  # how many of those were repeats
        self.timeouts = 0
        self.elapsed = 0.0

    @property
    def goodput(self):
        """Useful bytes per second, retransmissions not counted."""
        useful = (self.packets - self.retransmitted) * PAYLOAD
        return useful / self.elapsed if self.elapsed else 0.0


def _await_ack(channel, deadline, above):
    """Wait for an acknowledgement beyond `above`; None if the deadline passes.

    Acknowledgements that carry nothing new must not be mistaken for a
    timeout. With a window of packets in flight the receiver answers every
    one of them, so duplicates of an acknowledgement we have already acted on
    are entirely normal -- treating one as a lost packet would resend the
    whole window for no reason, and the extra traffic would produce still
    more duplicates.
    """
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return None
        channel.settimeout(remaining)
        try:
            datagram, _ = channel.recvfrom(BUFSIZE)
        except socket.timeout:
            return None
        kind, number, _ = unpack(datagram)
        if kind == KIND_ACK and number > above:
            return number
        # Stale or duplicate: ignore it and keep waiting for real news.


def stop_and_wait(channel, dest, count, rto=RTO):
    """One packet in flight at a time: the simplest thing that works."""
    payload = b"x" * PAYLOAD
    result = Result("stop-and-wait")
    start = time.monotonic()

    for seq in range(count):
        channel.sendto(pack(KIND_DATA, seq, payload), dest)
        result.packets += 1
        attempts = 1

        while True:
            ackno = _await_ack(channel, time.monotonic() + rto, seq)
            if ackno is not None:
                break  # acknowledged, move on to the next packet

            # Nothing came back in time. We cannot tell whether the packet or
            # its acknowledgement was lost, and it does not matter: send again.
            result.timeouts += 1
            attempts += 1
            if attempts > MAX_RETRIES:
                raise RuntimeError(f"gave up on packet {seq}")
            channel.sendto(pack(KIND_DATA, seq, payload), dest)
            result.packets += 1
            result.retransmitted += 1

    _finish(channel, dest, count, rto)
    result.elapsed = time.monotonic() - start
    return result


def go_back_n(channel, dest, count, rto=RTO, window=WINDOW):
    """Up to `window` packets in flight; one timer, for the oldest of them."""
    payload = b"x" * PAYLOAD
    result = Result(f"go-back-N (w={window})")
    start = time.monotonic()

    base = 0  # oldest packet not yet acknowledged
    nextseq = 0  # next packet never sent before
    stalls = 0

    while base < count:
        # Fill the window.
        while nextseq < base + window and nextseq < count:
            channel.sendto(pack(KIND_DATA, nextseq, payload), dest)
            result.packets += 1
            nextseq += 1

        ackno = _await_ack(channel, time.monotonic() + rto, base)
        if ackno is not None:
            base = ackno  # cumulative: everything below ackno is safe
            stalls = 0
            continue

        # The timer for the oldest packet expired, so go back to it and resend
        # the whole window -- the receiver has thrown away everything after
        # the gap anyway.
        result.timeouts += 1
        stalls += 1
        if stalls > MAX_RETRIES:
            raise RuntimeError(f"gave up at packet {base}")
        for seq in range(base, nextseq):
            channel.sendto(pack(KIND_DATA, seq, payload), dest)
            result.packets += 1
            result.retransmitted += 1

    _finish(channel, dest, count, rto)
    result.elapsed = time.monotonic() - start
    return result


def _finish(channel, dest, count, rto):
    """Announce the total. The closing handshake can be lost as well."""
    for _ in range(MAX_RETRIES):
        channel.sendto(pack(KIND_FIN, count), dest)
        channel.settimeout(rto)
        try:
            datagram, _ = channel.recvfrom(BUFSIZE)
        except socket.timeout:
            continue
        kind, _, _ = unpack(datagram)
        if kind == KIND_FINACK:
            return
    raise RuntimeError("receiver never confirmed the end of the transfer")


PROTOCOLS = {"sw": stop_and_wait, "gbn": go_back_n}


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else PORT
    name = sys.argv[3] if len(sys.argv) > 3 else "sw"
    count = int(sys.argv[4]) if len(sys.argv) > 4 else COUNT

    if name not in PROTOCOLS:
        sys.exit(f"usage: {sys.argv[0]} [host] [port] [sw|gbn] [packets]")

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        channel = LossyChannel(sock, seed=1)
        print(f"sending {count} packets with {name} to {host}:{port}")
        result = PROTOCOLS[name](channel, (host, port), count)

    print(f"--- {result.name} ---")
    print(f"  packets sent     {result.packets:>6}")
    print(f"  retransmitted    {result.retransmitted:>6}")
    print(f"  timeouts         {result.timeouts:>6}")
    print(f"  time             {result.elapsed:>6.2f} s")
    print(f"  goodput          {result.goodput / 1000:>6.1f} kB/s")


if __name__ == "__main__":
    main()
