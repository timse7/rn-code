"""QUIC client of the uppercase echo service.

    python quic_client.py [host] [port]

Reads one line from standard input, sends it on a QUIC stream and prints the
reply:

    echo "hello world" | python quic_client.py
"""

import asyncio
import ssl
import sys

from aioquic.asyncio import connect
from aioquic.quic.configuration import QuicConfiguration
from quic_common import ALPN, PORT

HOST = "localhost"
TIMEOUT = 5.0  # seconds for handshake and reply together


def _quiet_connection_errors(loop, context):
    """Keep one specific piece of asyncio noise out of the output.

    If nothing is listening on the port, the operating system answers the
    first datagram with an ICMP "port unreachable". aioquic surfaces that from
    a background task nobody awaits, and asyncio would then print an
    "exception was never retrieved" warning on top of our own error message.
    """
    if not isinstance(context.get("exception"), ConnectionError):
        loop.default_exception_handler(context)


async def ask(host, port, sentence):
    asyncio.get_running_loop().set_exception_handler(_quiet_connection_errors)

    configuration = QuicConfiguration(is_client=True, alpn_protocols=ALPN)
    # The server invents a new self-signed certificate on every start, so
    # there is nothing for the client to check it against. Switching
    # verification off is fine for a demo on localhost and unacceptable
    # anywhere else: it accepts *any* certificate, which is precisely what
    # TLS exists to prevent.
    configuration.verify_mode = ssl.CERT_NONE

    # connect() performs the QUIC handshake, which carries the TLS 1.3
    # handshake inside it -- one round trip for both together, where TLS over
    # TCP needs the TCP handshake first and the TLS one after it.
    async with connect(host, port, configuration=configuration) as client:
        reader, writer = await client.create_stream()
        writer.write(sentence.encode("utf-8"))
        writer.write_eof()  # tells the server the request is complete
        return await reader.read()


def main():
    host = sys.argv[1] if len(sys.argv) > 1 else HOST
    port = int(sys.argv[2]) if len(sys.argv) > 2 else PORT

    if sys.stdin.isatty():
        print("Type a sentence and press Enter:")
    sentence = sys.stdin.readline().rstrip("\n")
    if not sentence:
        sys.exit("nothing to send")

    try:
        reply = asyncio.run(asyncio.wait_for(ask(host, port, sentence), TIMEOUT))
    except asyncio.TimeoutError:
        sys.exit(f"no answer within {TIMEOUT} s -- is the server running?")

    print(f"FROM SERVER: {reply.decode('utf-8', errors='replace')}")


if __name__ == "__main__":
    main()
