"""Shared pieces of the reliable-transfer example: packets and a lossy channel.

Chapter 7 showed that UDP loses packets and tells nobody. Here we build, on
top of exactly the same UDP socket, the machinery that makes a transfer
reliable anyway: sequence numbers, acknowledgements, timeouts and
retransmission. That machinery is what a transport protocol like TCP adds.
"""

import heapq
import itertools
import random
import struct
import threading
import time

PORT = 9878
PAYLOAD = 1024  # bytes of application data per packet
COUNT = 100  # packets per transfer
WINDOW = 8  # go-back-N window, in packets
RTO = 0.15  # retransmission timeout, seconds
MAX_RETRIES = 30  # give up after this many timeouts in a row
LINGER = 0.5  # how long the receiver stays after a transfer, seconds

# Channel impairments, used by both endpoints unless overridden.
LOSS = 0.02  # probability that a datagram is dropped, per direction
DELAY = 0.010  # one-way delay, seconds
JITTER = 0.0  # extra random delay on top, seconds -- see the note below

HEADER = struct.Struct("!BI")  # kind, sequence number
KIND_DATA = 0
KIND_ACK = 1  # the number field is the next sequence number expected
KIND_FIN = 2  # the number field is the total number of data packets
KIND_FINACK = 3


def pack(kind, number, payload=b""):
    return HEADER.pack(kind, number) + payload


def unpack(datagram):
    kind, number = HEADER.unpack_from(datagram)
    return kind, number, datagram[HEADER.size :]


class LossyChannel:
    """A UDP socket that mistreats the datagrams passing through it.

    Real loss needs a real network: over loopback almost nothing goes missing,
    as chapter 7 demonstrates. So this channel drops and delays on purpose --
    driven by a seeded random generator, so that a run can be repeated exactly
    and two protocols can be compared under identical conditions.

    Delayed datagrams are held in a queue, ordered by the time they are due,
    and released by one background thread. That keeps the channel first-in
    first-out, which is what a single link does. Raise `jitter` above zero and
    datagrams start overtaking each other; the effect on go-back-N is worth
    seeing, because its receiver keeps no buffer and throws away everything
    that arrives early.

    The queue is a monitor, of the kind built in chapter 2: a condition
    variable guarding shared state, with a thread waiting on it.
    """

    def __init__(self, sock, loss=LOSS, delay=DELAY, jitter=JITTER, seed=0):
        self._sock = sock
        self._loss = loss
        self._delay = delay
        self._jitter = jitter
        self._random = random.Random(seed)
        self._queue = []  # heap of (due time, tie-breaker, datagram, address)
        self._order = itertools.count()  # keeps equal due times in send order
        self._condition = threading.Condition()
        self.delivered = 0
        self.dropped = 0

        pump = threading.Thread(target=self._pump, daemon=True)
        pump.start()

    def sendto(self, datagram, address):
        with self._condition:
            lost = self._random.random() < self._loss
            wait = self._delay + self._random.random() * self._jitter
            if lost:
                self.dropped += 1
                return  # the datagram simply never arrives, and nobody is told

            self.delivered += 1
            if wait <= 0:
                self._sock.sendto(datagram, address)
                return

            due = time.monotonic() + wait
            heapq.heappush(self._queue, (due, next(self._order), datagram, address))
            self._condition.notify()

    def _pump(self):
        """Release delayed datagrams, earliest first."""
        while True:
            with self._condition:
                while not self._queue:
                    self._condition.wait()

                due, _, datagram, address = self._queue[0]
                remaining = due - time.monotonic()
                if remaining > 0:
                    self._condition.wait(remaining)
                    continue  # re-check: something earlier may have arrived
                heapq.heappop(self._queue)

            try:
                self._sock.sendto(datagram, address)
            except OSError:
                pass  # socket already closed

    def recvfrom(self, bufsize):
        return self._sock.recvfrom(bufsize)

    def settimeout(self, timeout):
        self._sock.settimeout(timeout)
