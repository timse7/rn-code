"""TCP server of an uppercase echo service.

    python tcp_server.py [port]

The server must be running before any client can contact it. It waits on a
welcoming socket for connection requests; accept() then returns a *separate*
socket for the individual connection and leaves the welcoming socket free for
the next one. That is what lets one server talk to many clients: the
connections are told apart by the source address and port of each client.

This server handles one client at a time. Stop it with Ctrl-C.
"""

import socket
import sys

HOST = ""  # all local interfaces
PORT = 6789


def handle(connection_socket):
    """Uppercase every line the client sends, until the client goes away."""
    # TCP is a *byte stream*: recv() hands over whatever has arrived so far,
    # which may be half a line, one line, or three lines at once. Nothing in
    # TCP marks where a message ends -- the protocol on top has to, and here
    # that is the newline. makefile() wraps the socket in a buffered file
    # object that reassembles the stream into lines for us.
    with connection_socket.makefile("rw", encoding="utf-8", newline="\n") as stream:
        for line in stream:  # one iteration per line received
            sentence = line.rstrip("\n")
            print(f"received: {sentence!r}", flush=True)
            stream.write(sentence.upper() + "\n")
            stream.flush()  # the stream is buffered: without this nothing goes out


def serve(port):
    # AF_INET = IPv4, SOCK_STREAM = TCP
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as welcome_socket:
        # Without SO_REUSEADDR the port stays blocked for a minute or two after
        # the server exits, because the kernel keeps the old connection around
        # in TIME_WAIT.
        welcome_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        welcome_socket.bind((HOST, port))
        welcome_socket.listen()
        print(f"server listening on port {port}", flush=True)

        while True:
            # Blocks until a client connects. The connection itself is set up
            # by the kernel (the three-way handshake) before accept() returns.
            connection_socket, client_address = welcome_socket.accept()
            with connection_socket:  # closed again when this block is left
                print(f"connected: {client_address[0]}:{client_address[1]}", flush=True)
                handle(connection_socket)
            print("connection closed", flush=True)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    try:
        serve(port)
    except KeyboardInterrupt:
        print("\nserver stopped")


if __name__ == "__main__":
    main()
