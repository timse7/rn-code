"""Thread creation by subclassing threading.Thread.

Run it a few times: the order of the three lines is arbitrary, because the main
thread and the two worker threads run quasi-parallel.
"""

import threading


class MyThread(threading.Thread):
    """A thread with its work in run().

    Override run(), but never call it directly: that would be an ordinary
    method call in the *current* thread. Only start() forks a new thread.
    """

    def run(self):
        # Every thread has a name; unnamed ones get Thread-1, Thread-2, ...
        print(f"Hello, this is {self.name}")


def main():
    a = MyThread()
    b = MyThread()

    a.start()  # forks run() of a
    b.start()  # forks run() of b

    # Three threads now run quasi-parallel: a, b and the main thread.
    print(f"This is {threading.current_thread().name}")

    # join() merges the worker threads back into the main thread.
    a.join()
    b.join()


if __name__ == "__main__":
    main()
