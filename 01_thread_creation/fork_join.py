"""Fork and join, made visible.

Calling a procedure suspends the caller until it returns. Forking a thread does
not: caller and callee run on from the same point, each with its own stack.
join() suspends the caller until the target thread completes.

Expected output: P1 returns before main continues, whereas the forked P2 is
still running while main prints -- and main only waits for it at the join().
"""

import threading
import time


def p1():
    print("  P1: starts")
    time.sleep(0.2)
    print("  P1: returns")


def p2():
    print("  P2: starts")
    time.sleep(0.4)
    print("  P2: finishes")


def main():
    print("main: call P1 (main is suspended)")
    p1()  # ordinary call: main waits here
    print("main: P1 returned\n")

    print("main: fork P2 (main keeps running)")
    t = threading.Thread(target=p2, name="P2")
    t.start()  # fork: two threads from here on

    print("main: still running while P2 works")
    time.sleep(0.1)
    print(f"main: is P2 still alive? {t.is_alive()}")

    print("main: join P2 (main is suspended until P2 completes)")
    t.join()
    print("main: joined, one thread again")

    # Two more calls worth knowing:
    #   time.sleep(s)   suspends the calling thread for s *seconds*
    #   time.sleep(0)   gives up the CPU without really sleeping
    # There is no way to kill a thread from the outside, and that is deliberate:
    # a thread stopped at an arbitrary point could leave shared data half
    # updated or a lock held forever. A thread has to be *asked* to finish --
    # see the threading.Event stop flag used in the other examples.


if __name__ == "__main__":
    main()
