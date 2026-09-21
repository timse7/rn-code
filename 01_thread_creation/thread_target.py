"""Thread creation by handing the work to a thread, instead of subclassing it.

Any callable can be passed as the `target` of a Thread. The work and the thread
that runs it are separate things, so one work object can be given to several
threads -- as `work2do` is below.
"""

import threading


class MyWork:
    """The work to be done, not the thread itself.

    A class with __call__ keeps state together with the work, and one instance
    can be passed to any number of threads.
    """

    def __call__(self):
        # The work object is not the thread, so the name has to be asked of
        # whichever thread happens to be running us.
        print(f"Hello, this is {threading.current_thread().name}")


def greet():
    """The simplest form: a plain function as the thread's target."""
    print(f"Hello again, this is {threading.current_thread().name}")


def main():
    work2do = MyWork()
    a = threading.Thread(target=work2do)
    b = threading.Thread(target=work2do)

    a.start()
    b.start()
    print(f"This is {threading.current_thread().name}")

    # Same thing with a plain function; args=/kwargs= pass its arguments.
    c = threading.Thread(target=greet, name="worker-c")
    c.start()

    for t in (a, b, c):
        t.join()


if __name__ == "__main__":
    main()
