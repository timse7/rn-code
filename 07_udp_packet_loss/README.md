# 7. UDP packet loss

A sender that pushes 1024-byte packets out as fast as it can, and a receiver
that counts how many of them actually arrive. Nothing retransmits, nothing
acknowledges, nothing slows the sender down — so packets get lost, and the
point of the exercise is to see how many.

| File | Description |
|------|-------------|
| `udp_flood_client.py` | Sends N sequence-numbered packets at full speed, then announces the total |
| `udp_flood_server.py` | Counts arrivals, detects gaps, reports the loss |

Start the receiver in one terminal:

```bash
python udp_flood_server.py
```

and the sender in another:

```bash
python udp_flood_client.py
```

Sender:

```
sending 200000 packets of 1024 bytes to 127.0.0.1:9877
handed to the network 200000 packets in 0.83 s
  242,154 packets/s = 1983.7 Mbit/s
```

Receiver:

```
--- run finished ---
  sent by client        200000 packets
  received               99083 packets
  lost                  100917 packets (50.46 %)
  gaps in sequence      100917 packets
  reordered/dup              0 packets
  101.5 MB in 0.83 s = 976.5 Mbit/s
```

Half the data is simply gone, and neither side was told. Numbers vary from run
to run and from machine to machine.

Arguments: `udp_flood_client.py [host] [port] [packets]` and
`udp_flood_server.py [port] [work per packet in µs] [receive buffer]`.

## How the counting works

Each packet carries a 9-byte header — kind, sequence number, total — followed
by padding to exactly 1024 bytes. The receiver never keeps a list of the
sequence numbers it has seen; it only remembers the number it expects next:

```python
if seq == self.expected:  # the normal case
    self.expected += 1
elif seq > self.expected:  # jumped ahead: everything in between is missing
    self.gaps += seq - self.expected
    self.expected = seq + 1
else:  # older than something already seen
    self.late += 1
```

That is constant memory no matter how many packets are sent, and it is how
real protocols keep track. The authoritative loss figure comes from the end
markers the sender transmits after the run, announcing how many packets it
handed over; `gaps` computed independently should agree with it, and does.

The end marker can be lost as well. It is therefore sent five times, and the
receiver additionally gives up after three idle seconds and reports what it
has, flagging that the total is unknown.

## Where the packets actually disappear

The kernel holds arriving datagrams in the socket's receive buffer until the
program collects them. **When that buffer is full, every further datagram is
discarded** — no error at the sender, no notification at the receiver, no
entry anywhere. That is the whole mechanism, and it is the same thing that
happens in an overloaded router.

So loss needs someone who is too slow. The second argument of the receiver is
how long it pretends to work on each packet, and it drives the result
directly — measured on one laptop over loopback, 100,000 packets:

| Work per packet | Received | Lost |
|---|---|---|
| 0 µs | 100000 | 0.00 % |
| 5 µs (default) | 99083 | 50.46 % |
| 20 µs | 18316 | 81.68 % |

With `0` the receiver keeps up at about 226,000 packets/s and **nothing is
lost at all**, even with the receive buffer shrunk to 64 KB. That is worth
showing too: the loopback interface has no lossy link and no congested router,
so if the consumer is fast enough, nothing overflows. Loss is a queueing
phenomenon, not something UDP does on its own.

## Two traps this example walked into

Both were found by measuring, and both are easy to hit in an exercise:

* **Resolve the hostname once.** Passing `("localhost", 9877)` to `sendto()`
  makes the stack resolve the name again *for every packet*. That capped the
  sender at 13,000 packets/s — slower than the receiver, so nothing was ever
  lost and the demo showed 0 %. Resolving once with `getaddrinfo()` and
  sending to the numeric address raised it to 242,000 packets/s, and the loss
  appeared immediately.
* **A blocking socket does not send "as fast as it can".** When the receiver's
  queue is full, the kernel makes a blocking `sendto()` wait for room, which
  throttles the sender to exactly the receiver's pace — again 0 % loss. The
  client therefore sets `setblocking(False)`. The end markers are sent in
  blocking mode, where waiting is what we want.

If a packet cannot be handed over at all, `sendto()` reports `ENOBUFS` or
`EAGAIN`. The client counts those separately: they never left the machine, so
they are not network loss and must not be counted as sent.
