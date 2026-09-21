"""Dining philosophers demo.

    python fork_user.py [mon|sem|deadlock]

    mon        fork management as a monitor (default)
    sem        semaphores plus the `room` semaphore -- deadlock-free
    deadlock   semaphores without `room` -- deadlocks on purpose and says so

Five philosophers think and eat in a cycle. For eating a philosopher needs both
neighbouring forks.
"""

import random
import sys
import threading
import time

from forks_mon import Forks
from forks_sem import ForksSem, ForksSemDeadlock

N = 5  # philosophers, plates and forks
RUNTIME = 0.5  # seconds before main stops everybody

_print_lock = threading.Lock()


def log(message):
    with _print_lock:
        print(message)


class Philosopher(threading.Thread):
    """Thinks and eats in a cycle; eating needs both neighbouring forks."""

    def __init__(self, forks, process_id):
        super().__init__(name=f"Philosopher-{process_id}")
        self._forks = forks
        self.pid = process_id  # public: the driver prints per-philosopher stats
        self._running = threading.Event()
        self._running.set()
        self._rd = random.Random(process_id)  # reproducible per philosopher
        # Daemon threads are killed when the interpreter exits. Without this the
        # deadlock demo could never terminate: a philosopher blocked forever in
        # pick_up() would keep the process alive after main is done.
        self.daemon = True
        self.meals = 0

    def stop(self):
        self._running.clear()

    def run(self):
        while self._running.is_set():
            self._forks.pick_up(self.pid)
            self.meals += 1
            log(f"Philosopher-{self.pid} eating")
            time.sleep(self._rd.random() * 0.01)

            self._forks.put_down(self.pid)
            log(f"Philosopher-{self.pid} thinking")
            time.sleep(self._rd.random() * 0.1)
        log(f"Philosopher-{self.pid} stops")


def make_forks(choice):
    if choice == "mon":
        return Forks(N)
    if choice == "sem":
        return ForksSem(N)
    if choice == "deadlock":
        return ForksSemDeadlock(N, grab_delay=0.05)
    sys.exit(f"usage: {sys.argv[0]} [mon|sem|deadlock]")


def main():
    choice = sys.argv[1] if len(sys.argv) > 1 else "mon"
    forks = make_forks(choice)
    log(f"Using {type(forks).__name__} with {N} philosophers")
    if choice == "deadlock":
        log("This variant is expected to deadlock.")

    philosophers = [Philosopher(forks, i) for i in range(N)]
    for p in philosophers:
        p.start()

    time.sleep(RUNTIME)

    for p in philosophers:
        p.stop()
    for p in philosophers:
        # A philosopher blocked in pick_up() cannot notice the stop flag, so
        # this join() is where the deadlock variant hangs for good.
        p.join(timeout=1.0)
        if p.is_alive():
            log(f"{p.name} is stuck in pick_up() -- deadlock")

    stuck = [p for p in philosophers if p.is_alive()]
    if stuck:
        log(f"deadlock: {len(stuck)} of {N} philosophers hold one fork forever")

    log("main stops")
    log("meals: " + ", ".join(f"P{p.pid}={p.meals}" for p in philosophers))


if __name__ == "__main__":
    main()
