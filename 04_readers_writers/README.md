# 4. Readers/writers problem

In many applications there are many reads and few writes. Readers may all read
at the same time; a writer needs exclusive access. Plain mutual exclusion
cannot express that — it would serialise the readers too.

| File | Description |
|------|-------------|
| `rw.py` | Access control: entry/exit protocols with writer preference |
| `rw_user.py` | Reader and writer threads plus the driver |

```bash
python rw_user.py
```

Typical output:

```
total writes = 21
total reads  = 344
max. readers at the same time = 5
```

The last line records the largest number of threads ever inside `do_read()`
simultaneously. Reaching the number of reader threads is the evidence that
readers really do overlap — plain mutual exclusion would pin it to 1.

## The invariants

```
active_writers is 0 or 1
if active_writers == 1 then active_readers == 0
if waiting_writers > 0 then no new reader is let in
```

## Writer preference

`_allow_reader()` returns false while `waiting_writers > 0`, so a waiting
writer blocks all *new* readers and only has to wait for the readers already
active. Without that rule a steady stream of readers would starve every writer.
The price is symmetric: with it, a steady stream of writers starves the
readers. Which side to favour is an application decision, not a correctness
one.

## Two details in the implementation

* **`try`/`finally` around `do_read()`/`do_write()`.** If the operation raises
  and the exit protocol is skipped, the counters are never restored and every
  later writer blocks forever.
* **The statistics counter has its own lock.** Readers run concurrently by
  design, so `total_reads += 1` inside `do_read()` is a genuine race and needs
  protecting — deliberately *not* with the readers/writers lock, which would
  serialise the very thing the algorithm makes parallel.
