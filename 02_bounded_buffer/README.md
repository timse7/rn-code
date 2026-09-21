# 2. Bounded buffer (producer/consumer)

A buffer of finite capacity: producers block while it is full, consumers block
while it is empty. Two implementations of the same interface.

| File | Description |
|------|-------------|
| `bounded_buffer_mon.py` | Ring buffer as a monitor: `threading.Condition`, wait / notify_all |
| `semaphore.py` | Dijkstra's counting semaphore (`P`/`V`) built from a monitor |
| `bounded_buffer_sem.py` | Same buffer with three semaphores: `empty`, `full`, `mutex` |
| `buf_user.py` | Producer and consumer threads plus the driver |

```bash
python buf_user.py mon    # monitor variant (default)
python buf_user.py sem    # semaphore variant
```

## The two variants

* **Monitor.** One lock and one condition variable. Mutual exclusion and the
  waiting are handled by the same construct: a thread that cannot proceed calls
  `wait()`, which releases the lock, and re-checks its condition after being
  woken.
* **Semaphores.** Mutual exclusion and conditional synchronisation are split.
  `mutex` (initial value 1) protects the ring; `empty` (initial value `size`)
  counts the free slots and `full` (initial value 0) the filled ones, so a
  producer or consumer that has to wait does so *before* entering the critical
  section.

## Two things worth pointing out

* **Order of the P operations.** `empty.P(); mutex.P()` is correct;
  `mutex.P(); empty.P()` deadlocks, because a producer then falls asleep on a
  full buffer while still holding the mutex, and no consumer can get in to free
  a slot. See the note at the end of `bounded_buffer_sem.py`.
* **Conditional `notify_all()`.** Waking only on the empty→non-empty and
  full→non-full transition is safe only because *all* waiters are woken. The
  same code with `notify()` can deadlock, since the one thread woken may be
  another producer.

In production code the monitor variant is already available as
`queue.Queue(maxsize=n)`.
