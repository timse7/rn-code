"""Bounded buffer implemented with semaphores.

Three semaphores replace the monitor:

    empty   counts the free slots,   initially `size`   -- conditional sync.
    full    counts the filled slots, initially 0        -- conditional sync.
    mutex   binary semaphore,        initially 1        -- mutual exclusion

Neither method takes a lock of its own: mutual exclusion comes from `mutex`, and
the waiting is done by `empty`/`full` *before* the critical section is entered.
"""

from semaphore import Semaphore


class BoundedBufferSem:
    """Same interface as BoundedBufferMon, different synchronisation."""

    def __init__(self, size):
        if size <= 0:
            raise ValueError("buffer size must be > 0")
        self._data = [None] * size
        self._in = 0
        self._out = 0
        self._empty = Semaphore(size)
        self._full = Semaphore(0)
        self._mutex = Semaphore(1)

    def put(self, item):
        self._empty.P()  # take a free slot, wait if there is none
        self._mutex.P()  # enter the critical section

        self._data[self._in] = item
        self._in = (self._in + 1) % len(self._data)

        self._mutex.V()  # leave the critical section
        self._full.V()  # one more filled slot

    def get(self):
        self._full.P()  # take a filled slot, wait if there is none
        self._mutex.P()

        item = self._data[self._out]
        self._data[self._out] = None
        self._out = (self._out + 1) % len(self._data)

        self._mutex.V()
        self._empty.V()  # one more free slot
        return item


# The order of the two P operations matters. With
#
#     mutex.P(); empty.P()      # WRONG
#
# a producer that finds the buffer full falls asleep on empty.P() *while holding
# the mutex*, so no consumer can ever enter get() to free a slot: deadlock.
# Always acquire the counting semaphore first and the mutex second.
