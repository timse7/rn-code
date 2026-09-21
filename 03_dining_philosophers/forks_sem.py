"""Dining philosophers with semaphores.

Two fork managers with the same interface as the monitor version:

    ForksSemDeadlock   one semaphore per fork, taken left-then-right -> deadlock
    ForksSem           the same, plus a `room` semaphore of N-1      -> safe

Here the standard library's threading.Semaphore is used; P() is acquire() and
V() is release(). The hand-written equivalent is in
`../02_bounded_buffer/semaphore.py`.
"""

import threading
import time


class ForksSemDeadlock:
    """Deadlock and starvation danger -- the counter-example.

    Each fork is a binary semaphore. A philosopher takes the left fork first and
    then the right one. If every philosopher manages to take their left fork,
    everyone waits forever for a right fork that will never be released: the
    circular wait is closed.

    `grab_delay` makes that interleaving reliable enough to watch. With 0 the
    deadlock still happens, just not on every run.
    """

    def __init__(self, n, grab_delay=0.0):
        self._n = n
        self._forks = [threading.Semaphore(1) for _ in range(n)]
        self._grab_delay = grab_delay

    def _left(self, i):
        return (i - 1) % self._n

    def _right(self, i):
        return (i + 1) % self._n

    def pick_up(self, i):
        self._forks[self._left(i)].acquire()  # P
        time.sleep(self._grab_delay)  # only to expose the race
        self._forks[self._right(i)].acquire()  # P -- may never succeed

    def put_down(self, i):
        self._forks[self._left(i)].release()  # V
        self._forks[self._right(i)].release()  # V


class ForksSem:
    """Deadlock-free.

    `room` admits at most N-1 philosophers to the table at a time. With one seat
    fewer than philosophers, at least one of them always finds both forks free,
    so the circular wait can never close.

    This variant is often said to be free of starvation as well. That holds
    only if the semaphores hand the lock to waiters in FIFO order, which the
    built-in semaphore does not guarantee, so in practice a philosopher can
    still be unlucky for a long time.
    """

    def __init__(self, n):
        self._n = n
        self._forks = [threading.Semaphore(1) for _ in range(n)]
        self._room = threading.Semaphore(n - 1)

    def _left(self, i):
        return (i - 1) % self._n

    def _right(self, i):
        return (i + 1) % self._n

    def pick_up(self, i):
        self._room.acquire()  # room.P() -- enter the room
        self._forks[self._left(i)].acquire()
        self._forks[self._right(i)].acquire()

    def put_down(self, i):
        self._forks[self._left(i)].release()
        self._forks[self._right(i)].release()
        self._room.release()  # room.V() -- leave the room
