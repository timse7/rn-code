# 1. Thread creation

| File | Description |
|------|-------------|
| `thread_subclass.py` | Thread as a subclass of `threading.Thread`, overriding `run()` |
| `thread_target.py` | Work object handed to a thread via `target=` |
| `fork_join.py` | Call vs. fork vs. join, made visible |

```bash
python thread_subclass.py
python thread_target.py
python fork_join.py
```

## Two ways to say what a thread should do

* **Subclass `threading.Thread` and override `run()`.** The thread *is* the
  work. Convenient when the thread needs state of its own, as the producers,
  consumers and philosophers in the later chapters do.
* **Pass any callable as `target=`.** The work is separate from the thread that
  runs it, so the same work object can be handed to several threads.

Either way, `start()` forks the thread and `join()` waits for it. Calling
`run()` yourself is not an error, but it does not create a thread: the method
simply runs in the caller.

## A note on the GIL

CPython serialises the execution of Python bytecode with a global interpreter
lock, so threads give you concurrency — quasi-parallel execution on a shared
processor — rather than CPU parallelism. Everything in this chapter (critical
sections, monitors, semaphores) behaves exactly as described, and threads do
overlap during I/O and `sleep()`. For truly parallel CPU-bound work use
`multiprocessing`; since 3.13 CPython also offers an experimental free-threaded
build without the GIL.
