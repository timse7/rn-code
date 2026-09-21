"""TCP client of the uppercase echo service.

    python tcp_client.py [host] [port]

Reads one line from standard input, sends it to the server over a TCP
connection and prints the reply:

    echo "hello world" | python tcp_client.py
"""

import socket
import sys

HOST = "localhost"  # use the server's hostname if it runs elsewhere
PORT = 6789


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else PORT

    if sys.stdin.isatty():
        print("Type a sentence and press Enter:")
    sentence = sys.stdin.readline().rstrip("\n")
    if not sentence:
        sys.exit("nothing to send")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as client_socket:
        # connect() resolves the hostname, performs the three-way handshake and
        # only returns once the connection is up. Everything written afterwards
        # travels on that connection -- the address is not repeated per message.
        client_socket.connect((host, port))

        with client_socket.makefile("rw", encoding="utf-8", newline="\n") as stream:
            stream.write(sentence + "\n")  # the newline delimits the message
            stream.flush()
            modified = stream.readline().rstrip("\n")

    print(f"FROM SERVER: {modified}")


if __name__ == "__main__":
    main()
