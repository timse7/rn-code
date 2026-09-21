"""Dining philosophers, fork management as a monitor.

Free of deadlock, but not free of starvation.

The trick of this encoding: `free[i]` is not "is fork i on the table" but "how
many of philosopher i's two forks are currently free" (0, 1 or 2). Philosopher i
may eat only when free[i] == 2, and picking both forks up takes one free fork
away from each *neighbour*:

    free[left(i)] -= 1
    free[right(i)] -= 1

free[i] itself is deliberately left at 2 while i eats. That is harmless,
because free[i] is only ever read by philosopher i, who is busy eating and does
not call pick_up() again before put_down() has restored the counters.

Deadlock is impossible because both forks are taken *atomically* inside the
monitor -- nobody can be left holding one fork and waiting for the other.
"""

import threading


class Forks:
    def __init__(self, n):
        self._n = n
        self._free = [2] * n  # at the start all forks are on the table
        self._cond = threading.Condition()

    # Python's % is never negative, so the wrap-around needs no special case.
    def _left(self, i):
        return (i - 1) % self._n

    def _right(self, i):
        return (i + 1) % self._n

    def pick_up(self, i):
        with self._cond:
            while self._free[i] != 2:  # wait until both my forks are free
                self._cond.wait()
            self._free[self._left(i)] -= 1
            self._free[self._right(i)] -= 1

    def put_down(self, i):
        with self._cond:
            self._free[self._left(i)] += 1
            self._free[self._right(i)] += 1
            # notify_all() is not fair, so starvation remains possible: nothing
            # guarantees that the philosopher who has waited longest is the one
            # that gets the forks.
            self._cond.notify_all()
