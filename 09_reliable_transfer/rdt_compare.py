"""Run both protocols over the same channel and compare them.

    python rdt_compare.py [loss %] [packets]

Starts a receiver in a thread and sends the same number of packets with each
of the three protocols in turn, printing what each one cost. This is the
one-command version of the two-terminal demo; the protocols themselves are
the same code the sender and receiver use there.
"""

import socket
import sys
import threading

from rdt_common import COUNT, DELAY, JITTER, PAYLOAD, WINDOW, LossyChannel
from rdt_receiver import Receiver, SelectiveRepeatReceiver
from rdt_sender import go_back_n, selective_repeat, stop_and_wait

# Each sender needs the receiver that speaks its dialect of acknowledgement.
PAIRS = (
    (stop_and_wait, Receiver),
    (go_back_n, Receiver),
    (selective_repeat, SelectiveRepeatReceiver),
)


def run(protocol, receiver_class, count, loss, window):
    """Run one transfer end to end; return (result, receiver)."""
    receiver_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    receiver_socket.bind(("127.0.0.1", 0))  # any free port
    port = receiver_socket.getsockname()[1]

    # Two channels, two seeds: the two directions lose different datagrams.
    channel = LossyChannel(receiver_socket, loss, DELAY, JITTER, seed=2)
    receiver = receiver_class(channel)
    thread = threading.Thread(target=receiver.run_once, daemon=True)
    thread.start()

    sender_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sender_channel = LossyChannel(sender_socket, loss, DELAY, JITTER, seed=1)
    try:
        if protocol is stop_and_wait:
            result = protocol(sender_channel, ("127.0.0.1", port), count)
        else:
            result = protocol(sender_channel, ("127.0.0.1", port), count, window=window)
    finally:
        thread.join(timeout=15.0)
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

    header = f"{'protocol':<22}{'sent':>7}{'resent':>8}{'timeouts':>10}"
    print(header + f"{'time':>9}{'goodput':>11}")
    print("-" * len(header + f"{'time':>9}{'goodput':>11}"))

    results = []
    for protocol, receiver_class in PAIRS:
        result, receiver = run(protocol, receiver_class, count, loss, WINDOW)
        results.append(result)
        assert receiver.delivered == count, "the transfer was not reliable!"
        print(
            f"{result.name:<22}{result.packets:>7}{result.retransmitted:>8}"
            f"{result.timeouts:>10}{result.elapsed:>8.2f}s"
            f"{result.goodput / 1000:>9.1f} kB/s"
        )

    slowest = results[0]
    for result in results[1:]:
        if result.elapsed:
            print(
                f"\n{result.name} is "
                f"{slowest.elapsed / result.elapsed:.1f}x faster than "
                f"{slowest.name}."
            )
    print(f"\nEvery run delivered all {count} packets in order.")


if __name__ == "__main__":
    main()
