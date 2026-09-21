"""Sender for the reliable-transfer example, in two flavours.

    python rdt_sender.py [host] [port] [sw|gbn|sr] [packets]

    sw    stop-and-wait: one packet in flight, wait for its acknowledgement
    gbn   go-back-N: a window in flight, one timer, resend the whole window
    sr    selective repeat: a window in flight, a timer each, resend one

All three sit on a plain UDP socket and all three survive a lossy channel.
They differ in how many packets may be outstanding, and in what a lost packet
costs -- and the measurements show both.

`sr` needs the matching receiver: run `rdt_receiver.py <port> sr`.
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
    KIND_SACK,
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


def _await_sack(channel, deadline, acked):
    """Wait for an acknowledgement of a packet not yet acknowledged."""
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
        if kind == KIND_SACK and number not in acked:
            return number


def selective_repeat(channel, dest, count, rto=RTO, window=WINDOW):
    """Up to `window` packets in flight, each with its own timer.

    The difference to go-back-N is in what a timeout costs. Here only the one
    packet whose timer expired is sent again, because the receiver has kept
    everything else that arrived and said so packet by packet.
    """
    payload = b"x" * PAYLOAD
    result = Result(f"selective repeat (w={window})")
    start = time.monotonic()

    base = 0  # oldest packet not yet acknowledged
    nextseq = 0  # next packet never sent before
    sent_at = {}  # sequence number -> when it last went out
    acked = set()
    stalls = 0

    while base < count:
        while nextseq < base + window and nextseq < count:
            channel.sendto(pack(KIND_DATA, nextseq, payload), dest)
            sent_at[nextseq] = time.monotonic()
            result.packets += 1
            nextseq += 1

        outstanding = [s for s in range(base, nextseq) if s not in acked]
        if not outstanding:
            break  # everything sent has been acknowledged

        # The timer that expires first belongs to whichever packet went out
        # longest ago -- not necessarily the oldest one in the window.
        oldest = min(outstanding, key=sent_at.__getitem__)
        number = _await_sack(channel, sent_at[oldest] + rto, acked)

        if number is None:
            result.timeouts += 1
            stalls += 1
            if stalls > MAX_RETRIES:
                raise RuntimeError(f"gave up on packet {oldest}")
            channel.sendto(pack(KIND_DATA, oldest, payload), dest)
            sent_at[oldest] = time.monotonic()
            result.packets += 1
            result.retransmitted += 1
            continue

        acked.add(number)
        stalls = 0
        while base in acked:  # slide past everything now complete
            base += 1

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


PROTOCOLS = {"sw": stop_and_wait, "gbn": go_back_n, "sr": selective_repeat}


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else "127.0.0.1"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else PORT
    name = sys.argv[3] if len(sys.argv) > 3 else "sw"
    count = int(sys.argv[4]) if len(sys.argv) > 4 else COUNT

    if name not in PROTOCOLS:
        sys.exit(f"usage: {sys.argv[0]} [host] [port] [sw|gbn|sr] [packets]")

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
