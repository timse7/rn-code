# 3. Dining philosophers

Five philosophers sit at a table, thinking and eating in a cycle. There are
five forks, one between each pair of neighbours, and eating needs both of them.
Wanted: a protocol that excludes deadlock and starvation.

| File | Description |
|------|-------------|
| `forks_mon.py` | Fork management as a monitor — deadlock-free, starvation possible |
| `forks_sem.py` | `ForksSemDeadlock` and `ForksSem` with the `room` semaphore |
| `fork_user.py` | Philosopher threads and the driver |

```bash
python fork_user.py mon        # monitor variant (default)
python fork_user.py sem        # semaphores + room semaphore, deadlock-free
python fork_user.py deadlock   # semaphores without room: deadlocks on purpose
```

The `deadlock` run is the interesting one. It inserts a short delay between
taking the left and the right fork, so the circular wait closes on the very
first round; every philosopher ends up holding one fork and waiting forever for
the other, and the program reports it instead of just hanging:

```
deadlock: 5 of 5 philosophers hold one fork forever
meals: P0=0, P1=0, P2=0, P3=0, P4=0
```

## Why each variant behaves the way it does

* **Monitor** — both forks are taken *atomically* inside the critical section,
  so nobody can be left holding one fork. Deadlock is impossible by
  construction. `notify_all()` is not fair, so starvation is not excluded.
* **Semaphores without `room`** — left fork, then right fork. All five can
  succeed with their left fork; the circular wait is closed. Deadlock.
* **Semaphores with `room`** — at most `N-1` philosophers sit down at once, so
  at least one always finds both forks free and the cycle can never close.

Freedom from starvation is often claimed for the `room` variant too, but that
holds only if waiters are released in FIFO order, which the built-in semaphore
does not guarantee.

## The counter encoding in `forks_mon.py`

`free[i]` is not "is fork *i* on the table" but "how many of philosopher *i*'s
two forks are currently free" (0, 1 or 2). Philosopher *i* may eat only when
`free[i] == 2`, and picking both forks up takes one free fork away from each
neighbour. `free[i]` itself deliberately stays at 2 while *i* eats, which is
harmless: only *i* ever reads it, and *i* is busy eating until `put_down()` has
restored the counters.
