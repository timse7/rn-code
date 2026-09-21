"""Counting semaphore built from a monitor, after E. W. Dijkstra.

    P(s):  <await s > 0 -> s = s - 1>     entry
    V(s):  <s = s + 1>                    exit

with the semaphore invariant nP <= nV + IN, i.e. s = IN + nV - nP >= 0, where
nP and nV count the completed operations and IN is the initial value.

This class exists to show how a semaphore is built out of a monitor. In real
code use threading.Semaphore, which is exactly this, implemented in the
standard library: P() is acquire(), V() is release().
"""

import threading


class Semaphore:
    """Semaphore variable `s`, touchable only through P and V."""

    def __init__(self, initial_value=1):
        if initial_value < 0:
            raise ValueError("initial value must be >= 0")
        self._s = initial_value
        self._cond = threading.Condition()

    def P(self):  # noqa: N802 - Dijkstra's name
        """Entry: wait until s > 0, then decrement it."""
        with self._cond:
            while self._s <= 0:  # while, not if
                self._cond.wait()
            self._s -= 1  # s > 0 is guaranteed here

    def V(self):  # noqa: N802 - Dijkstra's name
        """Exit: increment s and wake one waiting thread."""
        with self._cond:
            self._s += 1
            # notify() is enough: every waiter is waiting for the same thing,
            # and one V() releases exactly one of them.
            self._cond.notify()

    # Aliases, so the class can stand in for threading.Semaphore.
    acquire = P
    release = V

    @property
    def value(self):
        """Current value of s -- for inspection in demos only."""
        with self._cond:
            return self._s
