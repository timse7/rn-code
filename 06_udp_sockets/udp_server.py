"""UDP server of an uppercase echo service.

    python udp_server.py [port]

There is no connection and no handshake here. The server binds a socket to a
port and waits for datagrams; every datagram carries the address of its sender,
which is the only way the server knows where to send the reply.

Stop it with Ctrl-C.
"""

import socket
import sys

HOST = ""  # all local interfaces
PORT = 9876
BUFSIZE = 2048


def serve(port):
    # AF_INET = IPv4, SOCK_DGRAM = UDP
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as server_socket:
        # No listen() and no accept(): there is nothing to connect to. One
        # socket serves every client.
        server_socket.bind((HOST, port))
        print(f"server listening on port {port}", flush=True)

        while True:
            # recvfrom() returns exactly the bytes of *one* datagram -- the
            # message boundary is preserved, so nothing has to be reassembled.
            # A datagram longer than BUFSIZE is silently truncated, though.
            data, client_address = server_socket.recvfrom(BUFSIZE)
            sentence = data.decode("utf-8", errors="replace")
            print(
                f"received {len(data)} byte(s) from "
                f"{client_address[0]}:{client_address[1]}: {sentence!r}",
                flush=True,
            )

            # The reply goes back to the address the datagram came from; it has
            # to be given explicitly on every send.
            server_socket.sendto(sentence.upper().encode("utf-8"), client_address)


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    try:
        serve(port)
    except KeyboardInterrupt:
        print("\nserver stopped")


if __name__ == "__main__":
    main()
