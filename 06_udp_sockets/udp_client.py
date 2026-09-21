"""UDP client of the uppercase echo service.

    python udp_client.py [host] [port]

Reads one line from standard input, sends it as a single datagram and prints
the reply:

    echo "hello world" | python udp_client.py
"""

import socket
import sys

HOST = "localhost"
PORT = 9876
BUFSIZE = 2048
TIMEOUT = 2.0  # seconds to wait for the reply


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else PORT

    if sys.stdin.isatty():
        print("Type a sentence and press Enter:")
    sentence = sys.stdin.readline().rstrip("\n")
    if not sentence:
        sys.exit("nothing to send")

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as client_socket:
        # UDP guarantees nothing: the request or the reply may be dropped on
        # the way and nobody is informed. Without a timeout recvfrom() would
        # then block forever, so a UDP client always needs one.
        client_socket.settimeout(TIMEOUT)

        # No connect() and no handshake -- the destination address is attached
        # to the datagram itself. Resolving the hostname to an IP address is
        # the one piece of network traffic that happens before this (DNS).
        client_socket.sendto(sentence.encode("utf-8"), (host, port))

        try:
            data, server_address = client_socket.recvfrom(BUFSIZE)
        except socket.timeout:
            sys.exit(f"no reply within {TIMEOUT} s -- request or reply lost?")

    print(f"FROM SERVER: {data.decode('utf-8', errors='replace')}")


if __name__ == "__main__":
    main()
