"""Why a selective-repeat window may be no wider than half the sequence space.

    python rdt_dilemma.py [window]

`rdt_sender.py` counts packets with a 32-bit sequence number that never wraps,
so the question of how wide its window may be never comes up. Every real
protocol header carries a small field instead, and then it does.

This is the same selective repeat with the sequence number cut to three bits --
eight values, 0 to 7 -- and the window arithmetic done modulo eight:

    python rdt_dilemma.py 4    # half the space: the transfer is correct
    python rdt_dilemma.py 7    # too wide: the receiver takes a retransmission
                               #           for new data and delivers garbage

With no argument it runs both and compares them.

Nothing here is random. The channel loses one scripted burst, the
acknowledgements for the very first window, because that is the case the rule
exists for; waiting for it to turn up by chance would take a long time. The
protocol logic itself is honest -- neither side is told anything a real
implementation would not know.
"""

import sys

MODULUS = 8  # sequence numbers 0..7, as a three-bit header field would give
COUNT = 9  # packets to transfer: enough to run past the wrap
ROUND_LIMIT = 40  # stop a transfer that is going nowhere


def in_window(seq, base, width, modulus):
    """Do the `width` sequence numbers starting at `base` include `seq`?

    This one line is the whole subject. The window can wrap past the end of
    the number space, so membership cannot be asked as `base <= seq < base +
    width`; it has to be asked as a distance measured forward from `base`.
    And a distance forward is all either side ever has to go on.
    """
    return (seq - base) % modulus < width


def window_of(base, width, modulus):
    """The sequence numbers a window covers, for printing."""
    return [(base + i) % modulus for i in range(width)]


class Receiver:
    """Selective repeat: delivers in order, buffers early arrivals.

    Acknowledges every packet by name rather than cumulatively, so the sender
    learns exactly what arrived. The only thing it has to decide whether an
    arriving packet is new or a duplicate is the sequence number in its
    header -- which is the point of the exercise.
    """

    def __init__(self, width, modulus):
        self.width = width
        self.modulus = modulus
        self.expected = 0  # sequence number of the next packet to deliver
        self.buffer = {}  # sequence number -> payload, held back for a gap
        self.delivered = []  # payloads handed to the application, in order

    def receive(self, seq, payload):
        """Take one packet. Returns (sequence number to acknowledge, note)."""
        if not in_window(seq, self.expected, self.width, self.modulus):
            # Outside the window, so as far as the receiver can tell it can
            # only be something already delivered. Acknowledge it again --
            # the sender evidently missed the first answer -- and hand over
            # nothing.
            return seq, "outside the window, discarded as a duplicate"

        held = seq in self.buffer
        self.buffer[seq] = payload

        handed = []
        while self.expected in self.buffer:
            handed.append(self.buffer.pop(self.expected))
            self.delivered.append(handed[-1])
            self.expected = (self.expected + 1) % self.modulus

        if handed:
            note = "delivered " + ", ".join(handed)
            if self.buffer:
                note += f" (still holding seq {sorted(self.buffer)})"
        elif held:
            note = "already buffered, kept"
        else:
            note = f"inside the window, buffered as early arrival ({payload})"
        return seq, note


class Sender:
    """Selective repeat: a window of packets in flight, a timer on each."""

    def __init__(self, width, modulus, count):
        self.width = width
        self.modulus = modulus
        self.count = count
        self.base = 0  # absolute number of the oldest unacknowledged packet
        self.next = 0  # absolute number of the next packet never sent
        self.acked = set()  # absolute numbers acknowledged so far

    def ready(self):
        """Packets that may go out now, by absolute number."""
        out = []
        while self.next < self.base + self.width and self.next < self.count:
            out.append(self.next)
            self.next += 1
        return out

    def oldest_unacked(self):
        """Whichever timer fires first -- nothing new fits until it does."""
        for number in range(self.base, self.next):
            if number not in self.acked:
                return number
        return None

    def ack(self, seq):
        """An acknowledgement names a sequence number; find the packet.

        The sender has the receiver's problem in reverse, and solves it the
        same way: only packets inside its own window are candidates, so the
        sender window has to be bounded too. That is why the rule is really
        `sender window + receiver window <= N`, and why equal windows make it
        `W <= N/2`.
        """
        for number in range(self.base, self.next):
            if number % self.modulus == seq:
                self.acked.add(number)
                break
        while self.base in self.acked:
            self.base += 1


def simulate(width, modulus=MODULUS, count=COUNT, trace=True):
    """Run one transfer. Returns the list of payloads the receiver delivered.

    Time runs in rounds, one round to a round trip. In each round the sender
    puts out whatever its window allows, or retransmits if nothing fits, the
    receiver answers, and the answers come back -- except in round one, where
    the whole burst of acknowledgements is lost.
    """
    sender = Sender(width, modulus, count)
    receiver = Receiver(width, modulus)
    lose_acks = True  # the scripted loss, round one only
    lines = []

    def log(label, text):
        lines.append(f"  {label:<9} {text}")

    rounds = 0
    while len(receiver.delivered) < count and rounds < ROUND_LIMIT:
        rounds += 1
        lines.append(f"round {rounds}")

        outgoing = sender.ready()
        if outgoing:
            span = f"{outgoing[0]}-{outgoing[-1]}" if len(outgoing) > 1 else outgoing[0]
            seqs = " ".join(str(n % modulus) for n in outgoing)
            log("send", f"packet {span} as seq {seqs}")
        else:
            number = sender.oldest_unacked()
            if number is None:
                break  # everything sent has been acknowledged
            outgoing = [number]
            log(
                "timeout",
                f"packet {number} still unacknowledged, resend as seq {number % modulus}",
            )

        acks = []
        for number in outgoing:
            seq = number % modulus
            window = window_of(receiver.expected, width, modulus)
            before = len(receiver.delivered)
            ack_seq, note = receiver.receive(seq, f"packet {number}")
            acks.append(ack_seq)

            # Only narrate the interesting arrivals: a full window of
            # in-order packets does not need a line each.
            if len(outgoing) == 1:
                log("receive", f"window is {window}, seq {seq} {note}")
            elif len(receiver.delivered) == before:
                log("receive", f"seq {seq} {note}")

        if len(outgoing) > 1:
            log("receive", f"delivered packet {outgoing[0]}-{outgoing[-1]}")
        log("expect", f"next wanted is seq {receiver.expected}")

        if lose_acks:
            log("ack", f"seq {' '.join(str(a) for a in acks)} -- ALL LOST")
            lose_acks = False
        else:
            for ack_seq in acks:
                sender.ack(ack_seq)
            log("ack", f"seq {' '.join(str(a) for a in acks)} arrived")

    if trace:
        print("\n".join(lines))
    return receiver.delivered


def report(width, modulus=MODULUS, count=COUNT, trace=True):
    """Run one transfer and say whether the data came through intact."""
    rule = "W <= N/2" if width * 2 <= modulus else "W > N/2, the rule is broken"
    print(f"N = {modulus} sequence numbers, W = {width}   ({rule})")
    print("-" * 64)

    delivered = simulate(width, modulus, count, trace)
    expected = [f"packet {n}" for n in range(count)]

    print()
    print("  delivered  " + ", ".join(d.replace("packet ", "") for d in delivered))
    print("  expected   " + ", ".join(e.replace("packet ", "") for e in expected))

    if delivered == expected:
        print("\n  OK -- every packet arrived once, in order.\n")
        return True

    for i, (got, want) in enumerate(zip(delivered, expected)):
        if got != want:
            print(
                f"\n  FAILED -- position {i} holds {got!r}, should be {want!r}."
                f"\n  The receiver took a retransmission of an old packet for a"
                f"\n  new one, because both landed on sequence number"
                f" {i % modulus}.\n"
            )
            return False
    print(f"\n  FAILED -- delivered {len(delivered)} packets, expected {count}.\n")
    return False


def main():
    if len(sys.argv) > 1:
        report(int(sys.argv[1]))
        return

    print(
        f"Selective repeat over a {MODULUS}-value sequence space, {COUNT} packets.\n"
        f"Both runs lose the same thing: every acknowledgement for the first\n"
        f"window. Only the window width differs.\n"
    )
    good = report(MODULUS // 2, trace=False)
    print()
    bad = report(MODULUS - 1, trace=True)

    print("=" * 64)
    if good and not bad:
        print(
            f"W = {MODULUS // 2} is the widest window this sequence space allows.\n"
            f"At W = {MODULUS - 1} the old and new receive windows overlap, so a\n"
            f"sequence number no longer says which packet it means."
        )
    else:
        print("Unexpected: see the runs above.")


if __name__ == "__main__":
    main()
