"""Producer/consumer demo for both bounded buffers.

    python buf_user.py [mon|sem]

NProc producers deposit timestamped messages into a shared buffer of NBUF slots;
one consumer takes them out. After a while main stops each producer, which then
deposits a "stop" sentinel so the consumer knows when to finish.
"""

import sys
import threading
import time

from bounded_buffer_mon import BoundedBufferMon
from bounded_buffer_sem import BoundedBufferSem

NPROC = 2  # number of producers
NBUF = 8  # buffer slots
RUNTIME = 0.1  # seconds each producer is allowed to run
STOP = "stop"  # sentinel: one per producer

# stdout is a shared resource, so printing is a critical section too -- without
# this lock the lines of concurrent threads can interleave mid-line.
_print_lock = threading.Lock()


def log(message):
    with _print_lock:
        print(message)


class Producer(threading.Thread):
    """Deposits timestamped messages until it is asked to stop."""

    def __init__(self, identifier, buffer):
        super().__init__(name=f"P-{identifier}")
        self._id = identifier
        self._buf = buffer
        # A plain boolean attribute would do here, but an Event says what it
        # is for, is safe to read from another thread, and can additionally be
        # waited on instead of polled.
        self._running = threading.Event()
        self._running.set()

    def stop(self):
        self._running.clear()

    def run(self):
        while self._running.is_set():
            message = f"P-{self._id}: {int(time.monotonic() * 1000) % 10000}"
            self._buf.put(message)
            time.sleep(self._id * 0.01 + 0.01)
        self._buf.put(STOP)  # tell the consumer that this producer is done


class Consumer(threading.Thread):
    """Takes messages until every producer has announced that it is done."""

    def __init__(self, identifier, buffer, n_producers):
        super().__init__(name=f"C-{identifier}")
        self._id = identifier
        self._buf = buffer
        self._running_producers = n_producers

    def run(self):
        while self._running_producers > 0:
            item = self._buf.get()
            log(f"C-{self._id} read: {item}")
            if item == STOP:
                self._running_producers -= 1  # one more producer has stopped


def main():
    choice = sys.argv[1] if len(sys.argv) > 1 else "mon"
    if choice == "mon":
        buffer = BoundedBufferMon(NBUF)
    elif choice == "sem":
        buffer = BoundedBufferSem(NBUF)
    else:
        sys.exit(f"usage: {sys.argv[0]} [mon|sem]")
    log(f"Using {type(buffer).__name__} with {NBUF} slots")

    producers = []
    for i in range(NPROC):  # create and fork the producers
        p = Producer(i, buffer)  # all of them share the same buffer
        producers.append(p)
        p.start()
        log(f"Starts {p.name}")

    consumer = Consumer(0, buffer, NPROC)
    consumer.start()
    log(f"Starts {consumer.name}")

    for p in producers:  # let them run, then stop and join them
        time.sleep(RUNTIME)
        p.stop()
        p.join()
        log(f"Stops {p.name}")

    consumer.join()
    log(f"Stops {consumer.name}")
    log(threading.current_thread().name)


if __name__ == "__main__":
    main()
