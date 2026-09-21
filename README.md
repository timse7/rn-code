# RN Code
Code for my computer networks (Rechnernetze) lecture at University of Klagenfurt (https://itec.aau.at/)

The examples are plain Python scripts, grouped by topic. Each folder is
self-contained and has its own README.

## Setup

```bash
make venv                 # create .venv and install dependencies
source .venv/bin/activate
```

Or without `make`:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

## Usage

```bash
python 01_thread_creation/thread_subclass.py    # run a single example
make format                                     # auto-format and fix imports (ruff)
make lint                                       # style and error checks (ruff)
make clean                                      # remove caches and build artifacts
```

Only the standard library is used (`threading`, `socket`, `abc`, `random`,
`time`), so every example also runs on a bare Python 3.9+ without the virtual
environment.

The socket examples come in pairs: start the server in one terminal and run
the client in another.

## Contents

### [1. Thread creation](01_thread_creation)

| File | Description |
|------|-------------|
| `thread_subclass.py` | Thread as a subclass of `threading.Thread`, overriding `run()` |
| `thread_target.py` | Work object handed to a thread via `target=` |
| `fork_join.py` | Call vs. fork vs. join, made visible |

### [2. Bounded buffer](02_bounded_buffer)

| File | Description |
|------|-------------|
| `bounded_buffer_mon.py` | Ring buffer as a monitor: `threading.Condition`, wait / notify_all |
| `semaphore.py` | Dijkstra's counting semaphore (`P`/`V`) built from a monitor |
| `bounded_buffer_sem.py` | Same buffer with the `empty`, `full` and `mutex` semaphores |
| `buf_user.py` | Producer and consumer threads plus the driver |

### [3. Dining philosophers](03_dining_philosophers)

| File | Description |
|------|-------------|
| `forks_mon.py` | Fork management as a monitor — deadlock-free |
| `forks_sem.py` | Semaphore variants with and without the `room` semaphore |
| `fork_user.py` | Philosopher threads and the driver; `deadlock` mode deadlocks on purpose |

### [4. Readers/writers](04_readers_writers)

| File | Description |
|------|-------------|
| `rw.py` | Access control with writer preference |
| `rw_user.py` | Reader and writer threads plus the driver |

### [5. TCP sockets](05_tcp_sockets)

| File | Description |
|------|-------------|
| `tcp_server.py` | Welcoming socket, one connection socket per client |
| `tcp_client.py` | Connects, sends a line, prints the reply |

### [6. UDP sockets](06_udp_sockets)

| File | Description |
|------|-------------|
| `udp_server.py` | One socket serving every client |
| `udp_client.py` | Sends a datagram, prints the reply, times out if none comes |

### [7. UDP packet loss](07_udp_packet_loss)

| File | Description |
|------|-------------|
| `udp_flood_client.py` | Sends 1024-byte packets as fast as it can, numbered |
| `udp_flood_server.py` | Counts arrivals, detects gaps, reports how many were lost |

## A note on the GIL

CPython serialises the execution of Python bytecode with a global interpreter
lock, so threads give concurrency — quasi-parallel execution on a shared
processor — rather than CPU parallelism. Critical sections, monitors and
semaphores behave exactly as described, and threads do overlap during I/O and
`sleep()`. For truly parallel CPU-bound work use `multiprocessing`; since 3.13
CPython also offers an experimental free-threaded build without the GIL.
