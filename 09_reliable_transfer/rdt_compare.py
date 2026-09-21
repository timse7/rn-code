"""Run both protocols over the same channel and compare them.

    python rdt_compare.py [loss %] [packets]

Starts a receiver in a thread, sends the same number of packets once with
stop-and-wait and once with go-back-N, and prints what each cost. This is the
one-command version of the two-terminal demo; the protocols themselves are
the same code the sender uses.
"""

import socket
import sys
import threading

from rdt_common import COUNT, DELAY, JITTER, PAYLOAD, WINDOW, LossyChannel
from rdt_receiver import Receiver
from rdt_sender import go_back_n, stop_and_wait


def run(protocol, count, loss, window):
    """Run one transfer end to end; return (result, receiver)."""
    receiver_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver_socket.bind(("127.0.0.1", 0))  # any free port
    port = receiver_socket.getsockname()[1]

    # Two channels, two seeds: the two directions lose different datagrams.
    receiver = Receiver(LossyChannel(receiver_socket, loss, DELAY, JITTER, seed=2))
    thread = threading.Thread(target=receiver.run_once, daemon=True)
    thread.start()

    sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    channel = LossyChannel(sender_socket, loss, DELAY, JITTER, seed=1)
    try:
        if protocol is go_back_n:
            result = go_back_n(channel, ("127.0.0.1", port), count, window=window)
        else:
            result = stop_and_wait(channel, ("127.0.0.1", port), count)
    finally:
        thread.join(timeout=10.0)
        sender_socket.close()
        receiver_socket.close()
    return result, receiver


def main():
    loss = float(sys.argv[1]) / 100 if len(sys.argv) > 1 else None
    count = int(sys.argv[2]) if len(sys.argv) > 2 else COUNT
    if loss is None:
        from rdt_common import LOSS

        loss = LOSS

    rtt = 2 * (DELAY + JITTER / 2)
    print(f"{count} packets of {PAYLOAD} bytes, {loss * 100:.0f} % loss per")
    print(f"direction, round trip about {rtt * 1000:.0f} ms\n")

    header = f"{'protocol':<18}{'sent':>7}{'resent':>8}{'timeouts':>10}"
    print(header + f"{'time':>9}{'goodput':>11}")
    print("-" * len(header + f"{'time':>9}{'goodput':>11}"))

    results = []
    for protocol in (stop_and_wait, go_back_n):
        result, receiver = run(protocol, count, loss, WINDOW)
        results.append(result)
        assert receiver.delivered == count, "the transfer was not reliable!"
        print(
            f"{result.name:<18}{result.packets:>7}{result.retransmitted:>8}"
            f"{result.timeouts:>10}{result.elapsed:>8.2f}s"
            f"{result.goodput / 1000:>9.1f} kB/s"
        )

    slow, fast = results
    if fast.elapsed:
        print(f"\ngo-back-N is {slow.elapsed / fast.elapsed:.1f}x faster here.")
    print(f"Every run delivered all {count} packets in order.")


if __name__ == "__main__":
    main()
