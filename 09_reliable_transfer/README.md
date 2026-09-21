# 9. Reliable data transfer over UDP

Chapter 7 ended by proving that UDP throws away half the data and tells
nobody. This chapter builds, on top of exactly the same UDP socket, the
machinery that makes a transfer reliable anyway — sequence numbers,
acknowledgements, timeouts, retransmission — and then asks how fast it can be
made to go. That machinery is what a transport protocol like TCP adds.

| File | Description |
|------|-------------|
| `rdt_common.py` | Packet format and the deliberately lossy channel |
| `rdt_receiver.py` | Two receivers: cumulative, and one that buffers early arrivals |
| `rdt_sender.py` | Three senders: stop-and-wait, go-back-N, selective repeat |
| `rdt_compare.py` | Runs all three over the same channel and compares them |

The quickest look, one command:

```bash
python rdt_compare.py
```

```
100 packets of 1024 bytes, 2 % loss per direction, round trip about 20 ms

protocol                 sent  resent  timeouts     time    goodput
-------------------------------------------------------------------
stop-and-wait             103       3         3    3.06s     33.5 kB/s
go-back-N (w=8)           108       8         1    0.50s    206.6 kB/s
selective repeat (w=8)    103       3         3    0.90s    114.3 kB/s

Every run delivered all 100 packets in order.
```

Or the two-terminal version, like the other socket chapters:

```bash
python rdt_receiver.py                       # terminal 1
python rdt_sender.py 127.0.0.1 9878 sw 100   # terminal 2
python rdt_sender.py 127.0.0.1 9878 gbn 100
```

Selective repeat needs the receiver that speaks its dialect:

```bash
python rdt_receiver.py 9878 sr               # terminal 1
python rdt_sender.py 127.0.0.1 9878 sr 100   # terminal 2
```

The receiver is as much part of a protocol as the sender. Pair them wrongly
and the transfer stalls -- which is itself worth demonstrating once.

## Why the window is the whole story

Stop-and-wait puts exactly one packet in the air and then waits a full round
trip for its acknowledgement. Its speed is therefore one packet per RTT, no
matter how fast the link is: 1024 bytes per 20 ms is 51 kB/s, and that is what
the measurement shows — the network is idle almost the entire time.

Go-back-N keeps up to `WINDOW` packets unacknowledged, so it gets `WINDOW`
packets per RTT. The right window is the **bandwidth-delay product**: enough
packets in flight to keep the link busy for one full round trip. Raise
`WINDOW` in `rdt_common.py` and watch the time fall until something else
becomes the limit.

## What loss does to them

Same 100 packets, same channel, only the loss rate changed. Time first:

| Loss per direction | stop-and-wait | go-back-N | selective repeat |
|---|---|---|---|
| 0 % | 2.51 s | 0.34 s | 0.35 s |
| 2 % | 3.06 s | **0.50 s** | 0.90 s |
| 5 % | 5.35 s | **1.48 s** | 1.65 s |
| 10 % | 7.45 s | 2.93 s | **2.41 s** |
| 20 % | 11.81 s | 3.99 s | **2.56 s** |
| 30 % | 19.06 s | 6.72 s | **6.50 s** |

Every single run delivered all 100 packets in order — that is the reliability
part working, under conditions where a third of everything disappears.

Now the more telling column, the number of packets actually put on the wire
to deliver those 100:

| Loss per direction | stop-and-wait | go-back-N | selective repeat |
|---|---|---|---|
| 5 % | 119 | 156 | 119 |
| 10 % | 133 | 223 | 133 |
| 20 % | 162 | 276 | 162 |
| 30 % | 210 | 400 | 210 |

**Selective repeat sends exactly as many packets as stop-and-wait, and takes
roughly as long as go-back-N.** It has the efficiency of the one and the speed
of the other, and that is the entire reason it exists. Its count is the
minimum possible: 100 packets plus one retransmission per loss.

Go-back-N pays for its single timer. One missing packet makes the sender *go
back* and repeat the whole window, because the receiver keeps no buffer and
has thrown away everything after the gap — and at high loss the resent window
loses something again, so it repeats once more. At 30 % loss it puts 400
packets on the wire to deliver 100.

Below about 5 % loss go-back-N is still marginally faster in wall-clock terms,
because with few losses the wasted retransmissions cost little and cumulative
acknowledgements recover a gap in one step. The crossover here is around
10 %. What tips it is bandwidth, not latency: go-back-N wastes it, selective
repeat does not.

## The two changes that make selective repeat

Both are in `SelectiveRepeatReceiver`, and they are small:

* **The receiver keeps a buffer.** A packet that arrives before the gap ahead
  of it is stored, not discarded, and handed over once the gap is filled. The
  `most ever buffered` line in its output shows the buffer in use.
* **Acknowledgements name a packet, not a position.** `KIND_SACK` carries the
  sequence number that actually arrived, so the sender learns exactly which
  one is still missing instead of only "everything below n".

The sender then keeps a timer per packet rather than one for the window, and
on a timeout resends that one packet alone. The price of all this is the
buffer and the bookkeeping — which is why go-back-N is worth teaching first.

## Reordering hurts more than loss

The channel is first-in first-out by default. Give it jitter so datagrams can
overtake each other, and then, **with no loss at all**:

| Jitter | protocol | time | resent | discarded | most buffered |
|---|---|---|---|---|---|
| 0 ms | go-back-N | 0.34 s | 0 | 0 | — |
| 0 ms | selective repeat | 0.34 s | 0 | 0 | 1 |
| 6 ms | go-back-N | **10.83 s** | **465** | 465 | — |
| 6 ms | selective repeat | **0.41 s** | **0** | 0 | 8 |

Nothing was lost in any of those runs. Every packet arrived — just not in
order. Go-back-N slows down by a factor of 32 and resends 465 packets it had
already delivered successfully, because its receiver discards everything that
arrives early and the sender has no way to learn that.

Selective repeat does not notice at all: not one retransmission. Its buffer
fills to the full window of 8 and empties again as the gaps close, which is
exactly what the buffer is for. Reordering is where the two designs differ
most sharply, and it costs nothing to demonstrate.

## Details worth pointing at

* **The channel has to lie on purpose.** Over loopback almost nothing is lost
  (chapter 7 measured this), so `LossyChannel` drops and delays deliberately,
  driven by a seeded generator so a run can be repeated exactly and two
  protocols compared under identical conditions. Its delay queue is a monitor
  of the kind built in chapter 2: a condition variable guarding a heap, with
  one thread waiting on it.
* **Acknowledgements are cumulative.** An acknowledgement carries the number
  of the next packet still wanted, so "I have everything below n". A lost
  acknowledgement then costs nothing as long as a later one gets through —
  which is why the receiver answers duplicates too.
* **A timeout does not say what went missing.** The sender cannot tell whether
  its packet or the acknowledgement was lost, and does not need to: it sends
  again either way. The receiver recognises the duplicate by its sequence
  number.
* **Somebody has to answer last.** When the sender announces the end of the
  transfer, the receiver's confirmation can be lost like anything else, and
  the sender asks again — so the receiver lingers briefly and keeps answering
  instead of leaving at once. Leaving immediately strands the sender, which is
  exactly why TCP holds a closed connection in `TIME_WAIT`.
