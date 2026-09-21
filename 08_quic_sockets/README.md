# 8. QUIC sockets

The same uppercase echo service once more, this time over QUIC. The client
sends a line, the server sends it back in capitals — identical behaviour to
chapters 5 and 6, so the differences are all in the protocol.

| File | Description |
|------|-------------|
| `quic_common.py` | ALPN name, port, and the throwaway self-signed certificate |
| `quic_server.py` | Listens on UDP 4433, one handler per stream |
| `quic_client.py` | Opens a stream, sends one line from standard input, prints the reply |

**This chapter needs a third-party library.** Chapters 1–7 run on a bare
Python; this one does not, because QUIC is not in the standard library:

```bash
make venv && source .venv/bin/activate
```

Start the server in one terminal:

```bash
python quic_server.py
```

and the client in another:

```bash
echo "hello world" | python quic_client.py
```

```
FROM SERVER: HELLO WORLD
```

Arguments: `quic_server.py [port]` and `quic_client.py [host] [port]`.

## It really is UDP underneath

While the server runs:

```
$ lsof -nP -iUDP | grep 4433
Python  3818 timse    7u  IPv4 ...  UDP 127.0.0.1:4433
```

One plain UDP socket, exactly like chapter 6. Everything that makes QUIC
reliable — acknowledgements, retransmission, ordering, flow control,
congestion control — happens *above* that socket, in the library, in user
space. In TCP all of that sits in the kernel, which is why TCP changes ship
with operating systems and QUIC changes ship with applications.

## What is different from TCP

* **Encryption is not optional.** There is no plaintext QUIC. The server
  cannot start without a certificate and a key, which is why this chapter has
  a `quic_common.py` and the TCP one does not.
* **One handshake instead of two.** The TLS 1.3 handshake is carried inside
  the QUIC handshake, so a connection is usable after one round trip. TLS over
  TCP needs the TCP handshake first and the TLS handshake after it.
* **Streams, not one byte stream.** A connection carries many independent
  streams. Each has an explicit end, so `read()` returns without needing a
  delimiter — compare the newline framing the TCP example had to invent. A
  lost packet stalls only the stream it belonged to, not the others, which is
  the head-of-line blocking that TCP cannot avoid.
* **Connections are identified by a connection ID**, not by the
  address/port 4-tuple, so a connection can survive a client changing network.

## About that certificate

The server generates a fresh self-signed certificate in memory on every start.
Nothing touches the disk, and no private key is committed to this repository.

The consequence is that the client has nothing to verify the certificate
against, so it sets:

```python
configuration.verify_mode = ssl.CERT_NONE
```

That accepts *any* certificate, including an attacker's, which is exactly what
TLS exists to prevent. It is fine for a demo talking to localhost and wrong
everywhere else. In production the server presents a certificate signed by a
CA the client already trusts, and `verify_mode` stays at its default.
