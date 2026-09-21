# 6. UDP sockets

The same uppercase echo service, over UDP: unreliable datagrams, no connection.

| File | Description |
|------|-------------|
| `udp_server.py` | One socket bound to port 9876, serving every client |
| `udp_client.py` | Sends one line from standard input as a datagram, prints the reply |

Start the server in one terminal:

```bash
python udp_server.py
```

and the client in another:

```bash
echo "hello world" | python udp_client.py
```

```
FROM SERVER: HELLO WORLD
```

Both take arguments: `udp_server.py [port]` and `udp_client.py [host] [port]`.

## No connection, so the address travels with the data

There is no handshake, no `listen()`, no `accept()` and no per-client socket.
The client attaches the destination address to every datagram it sends, and
the server reads the sender's address out of every datagram it receives — that
is the only way it knows where to send the reply.

## Message boundaries are preserved

`recvfrom()` returns exactly the bytes of one datagram. What was sent as one
`sendto()` arrives as one `recvfrom()`, so unlike TCP there is nothing to
reassemble and no delimiter is needed. The catch is at the other end: a
datagram longer than the receive buffer is silently truncated, and the rest is
gone.

The server log also shows why a buffer is sized in bytes, not characters:

```
received 22 byte(s) from 127.0.0.1:59408: 'grüße aus klagenfurt'
```

20 characters, 22 bytes — `ü` and `ß` take two bytes each in UTF-8.

## Unreliability is the application's problem

A datagram can be dropped, duplicated or overtaken, and nobody is told. If the
request or the reply is lost, a client that just calls `recvfrom()` waits
forever, so `udp_client.py` sets a timeout:

```bash
echo "hello" | python udp_client.py localhost 9999    # nothing listening there
no reply within 2.0 s -- request or reply lost?
```

Anything more — retransmitting, detecting duplicates, putting datagrams back in
order — has to be built on top, which is essentially what TCP does for you.

Chapter 7 makes this measurable: a sender at full speed against a receiver
that cannot keep up loses about half of its packets, and neither side is
told.

## Compared with TCP

| | TCP | UDP |
|---|---|---|
| Connection | handshake in `connect()`/`accept()` | none |
| Server sockets | welcoming socket + one per client | a single socket |
| Addressing | once, at connection setup | on every datagram |
| Delivery | reliable, in order | may be lost, duplicated, reordered |
| Data model | byte stream, needs delimiters | datagrams, boundaries preserved |
| Too much data | stream is split and reassembled | datagram is truncated |
| Client timeout | optional | practically mandatory |
