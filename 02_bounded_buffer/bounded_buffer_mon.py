"""Bounded buffer implemented as a monitor.

The buffer is a ring of fixed capacity. `_in` and `_out` point at the next
empty resp. filled slot, `_used` counts the filled slots; both pointers are
advanced modulo the length.

A monitor bundles the shared data, the lock protecting it and the condition
threads wait on. threading.Condition is exactly that:

    with self._cond:           enter the critical section
    self._cond.wait()          leave it and wait until woken
    self._cond.notify_all()    wake every waiting thread
"""

import threading


class BoundedBufferMon:
    """Producers deposit via put(), consumers take via get(); both may block."""

    def __init__(self, size):
        if size <= 0:
            raise ValueError("buffer size must be > 0")
        self._data = [None] * size
        self._in = 0
        self._out = 0
        self._used = 0
        self._cond = threading.Condition()

    def put(self, item):
        """Deposit one item, waiting while the buffer is full."""
        with self._cond:  # entry protocol: enter the critical section
            # `while`, never `if`: after being woken the lock has been regained,
            # but another thread may have changed the condition in between, so
            # the condition has to be re-checked.
            while self._used == len(self._data):
                self._cond.wait()  # leaves the CS until woken

            self._data[self._in] = item
            self._in = (self._in + 1) % len(self._data)  # advance ring pointer
            self._used += 1

            if self._used == 1:  # buffer *was* empty -> wake waiting consumers
                self._cond.notify_all()
        # exit protocol: leaving the `with` block releases the lock

    def get(self):
        """Take one item, waiting while the buffer is empty."""
        with self._cond:
            while self._used == 0:
                self._cond.wait()

            item = self._data[self._out]
            self._data[self._out] = None  # drop the reference, help the GC
            self._out = (self._out + 1) % len(self._data)
            self._used -= 1

            if self._used == len(self._data) - 1:  # was full -> wake producers
                self._cond.notify_all()

            return item

    def __len__(self):
        with self._cond:
            return self._used


# Two remarks on the conditional notify_all() above:
#
#  * Notifying only on the empty->non-empty and full->non-full transitions is an
#    optimisation. It is safe *only* because producers and consumers wait on the
#    same condition variable and notify_all() wakes every one of them. With a
#    plain notify() the program could deadlock: the single thread woken might be
#    another producer. An unconditional notify_all() is always correct.
#  * The standard library already ships this class as queue.Queue(maxsize=n),
#    with put()/get() behaving exactly like the two methods above. Use it in
#    real code; this file is here to show what is inside it.
