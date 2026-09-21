# 5. TCP sockets

An uppercase echo service: the client sends a line, the server sends it back
in capitals. TCP gives a reliable, connection-oriented byte stream.

| File | Description |
|------|-------------|
| `tcp_server.py` | Welcoming socket on port 6789, one connection socket per client |
| `tcp_client.py` | Connects, sends one line from standard input, prints the reply |

Start the server in one terminal:

```bash
python tcp_server.py
```

and the client in another:

```bash
echo "hello world" | python tcp_client.py
```

```
FROM SERVER: HELLO WORLD
```

Both take arguments: `tcp_server.py [port]` and `tcp_client.py [host] [port]`.
Run the client without piped input and it prompts for a line.

## Two sockets on the server

The server creates one **welcoming socket**, bound to a well-known port, and
calls `accept()` on it. Each accepted client gets its own **connection
socket**, while the welcoming socket immediately goes back to waiting. That is
how a server talks to many clients at once; connections are told apart by the
client's address and source port, which is why the log shows a different port
for every run.

The client needs no bind: it names the server's host and port in `connect()`,
and the operating system picks a free source port for it.

## TCP is a byte stream, not a sequence of messages

`recv()` returns whatever has arrived so far — possibly half a line, possibly
three lines at once. TCP guarantees that all bytes arrive, in order, but not
that they arrive in the same chunks they were sent in. Where a message ends is
the job of the protocol on top; here a newline marks it, and `makefile()`
reassembles the stream into lines.

This is the central difference to the datagrams in the next chapter, and the
reason application protocols need length fields or delimiters.

## One client at a time

`handle()` runs to completion before the next `accept()`, so a second client
waits. Making the server concurrent is a three-line change with the threads
from chapter 1:

```python
connection_socket, client_address = welcome_socket.accept()
t = threading.Thread(target=handle, args=(connection_socket,), daemon=True)
t.start()
```

## SO_REUSEADDR

After the server exits, the kernel keeps the connection in `TIME_WAIT` for a
minute or two to catch stray packets, and the port stays blocked. Setting
`SO_REUSEADDR` before `bind()` allows an immediate restart — without it,
restarting the server during a lecture fails with "Address already in use".
