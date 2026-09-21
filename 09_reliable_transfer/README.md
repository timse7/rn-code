# 9. Reliable data transfer over UDP

Chapter 7 ended by proving that UDP throws away half the data and tells
nobody. This chapter builds, on top of exactly the same UDP socket, the
machinery that makes a transfer reliable anyway — sequence numbers,
acknowledgements, timeouts, retransmission — and then asks how fast it can be
made to go. That machinery is what a transport protocol like TCP adds.

| File | Description |
|------|-------------|
| `rdt_common.py` | Packet format and the deliberately lossy channel |
| `rdt_receiver.py` | Receiver, shared by both protocols; cumulative acknowledgements |
| `rdt_sender.py` | Sender, in two flavours: stop-and-wait and go-back-N |
| `rdt_compare.py` | Runs both over the same channel and compares them |

The quickest look, one command:

```bash
python rdt_compare.py
```

```
100 packets of 1024 bytes, 2 % loss per direction, round trip about 20 ms

protocol             sent  resent  timeouts     time    goodput
---------------------------------------------------------------
stop-and-wait         103       3         3    3.07s     33.3 kB/s
go-back-N (w=8)       108       8         1    0.49s    207.2 kB/s

go-back-N is 6.2x faster here.
Every run delivered all 100 packets in order.
```

Or the two-terminal version, like the other socket chapters:

```bash
python rdt_receiver.py                       # terminal 1
python rdt_sender.py 127.0.0.1 9878 sw 100   # terminal 2
python rdt_sender.py 127.0.0.1 9878 gbn 100
```

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

## What loss does to it

Same 100 packets, same channel, only the loss rate changed:

| Loss per direction | stop-and-wait | go-back-N (w=8) | speed-up |
|---|---|---|---|
| 0 % | 2.51 s | 0.34 s | 7.4× |
| 2 % | 3.07 s | 0.49 s | 6.3× |
| 5 % | 5.34 s | 1.48 s | 3.6× |
| 10 % | 7.46 s | 2.94 s | 2.5× |
| 20 % | 11.84 s | 4.00 s | 3.0× |

Every one of those runs delivered all 100 packets in order — that is the
reliability part working. But the advantage shrinks as loss grows, and the
reason is in the name: one missing packet makes the sender *go back* and
repeat the whole window, because the receiver keeps no buffer and has thrown
away everything after the gap. At 10 % loss go-back-N sends 223 packets to
deliver 100. Selective repeat — buffer the out-of-order packets, resend only
what is actually missing — is the answer, and the natural next exercise.

## Reordering hurts more than loss

The channel is first-in first-out by default. Give it jitter so datagrams can
overtake each other, and then, **with no loss at all**:

| Jitter | go-back-N | Resent | Discarded by receiver |
|---|---|---|---|
| 0 ms | 0.34 s | 0 | 0 |
| 6 ms | 10.85 s | 465 | 465 |

Nothing was lost. Every packet arrived — just not in order, and a receiver
without a buffer discards everything that arrives early, so the sender has to
send it all again. This is worth showing precisely because it is
counter-intuitive.

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
