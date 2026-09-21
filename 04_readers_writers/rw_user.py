"""Readers/writers demo.

    python rw_user.py

Five readers and two writers hammer a shared object for half a second; the
subclass simply counts the accesses. At the end the totals are printed, plus
the largest number of readers that were ever inside do_read() at the same
time -- the evidence that readers really do overlap.
"""

import random
import threading
import time

from rw import RW

NREADERS = 5
NWRITERS = 2
RUNTIME = 0.5  # seconds before main stops everybody

_print_lock = threading.Lock()


def log(message):
    with _print_lock:
        print(message)


class RWUser(RW):
    """A trivial shared object: reading and writing just count the accesses."""

    def __init__(self):
        super().__init__()
        self.total_reads = 0
        self.total_writes = 0
        self.max_concurrent_readers = 0
        # Readers run *concurrently* by design, so this counter needs a
        # critical section of its own -- incrementing it unprotected would be a
        # plain race. It must not be the readers/writers lock, which would
        # serialise exactly what the algorithm makes parallel.
        self._stats_lock = threading.Lock()

    def do_read(self):
        with self._stats_lock:
            self.total_reads += 1
            self.max_concurrent_readers = max(
                self.max_concurrent_readers, self.active_readers
            )
        time.sleep(0.001)  # pretend the read takes a moment

    def do_write(self):
        # No lock needed: write() guarantees exclusive access.
        self.total_writes += 1
        time.sleep(0.001)


class ReaderThread(threading.Thread):
    """Reads in a loop until it is asked to stop."""

    def __init__(self, rw_control):
        super().__init__()
        self._rw = rw_control
        self._running = threading.Event()
        self._running.set()
        self._rd = random.Random()
        self.count = 0

    def stop(self):
        self._running.clear()

    def run(self):
        while self._running.is_set():
            self._rw.read()
            self.count += 1
            log(f"{self.name}-read: {self.count}")
            time.sleep(self._rd.random() * 0.01)
        log(f"Reader-{self.name} stops")


class WriterThread(threading.Thread):
    """Writes in a loop until it is asked to stop."""

    def __init__(self, rw_control):
        super().__init__()
        self._rw = rw_control
        self._running = threading.Event()
        self._running.set()
        self._rd = random.Random()
        self.count = 0

    def stop(self):
        self._running.clear()

    def run(self):
        while self._running.is_set():
            self._rw.write()
            self.count += 1
            log(f"{self.name}-write: {self.count}")
            time.sleep(self._rd.random() * 0.1)
        log(f"Writer-{self.name} stops")


def main():
    rw_control = RWUser()

    writers = [WriterThread(rw_control) for _ in range(NWRITERS)]
    readers = [ReaderThread(rw_control) for _ in range(NREADERS)]
    for w in writers:
        w.start()
    for r in readers:
        r.start()

    time.sleep(RUNTIME)

    for t in writers + readers:
        t.stop()
    for t in writers + readers:
        t.join()

    log(f"total writes = {rw_control.total_writes}")
    log(f"total reads  = {rw_control.total_reads}")
    log(f"max. readers at the same time = {rw_control.max_concurrent_readers}")


if __name__ == "__main__":
    main()
