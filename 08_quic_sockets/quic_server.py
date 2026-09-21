"""QUIC server of an uppercase echo service.

    python quic_server.py [port]

QUIC runs on top of UDP: this program opens a single UDP socket, and
everything else -- reliability, ordering, flow control, streams, encryption --
happens above it, inside this process rather than in the kernel.

A client opens a stream, sends a sentence and ends the stream; the server
sends it back in capitals. Several streams can be in flight on one connection
at the same time and are handled independently of each other.

Stop it with Ctrl-C.
"""

import asyncio
import sys

from aioquic.asyncio import serve
from aioquic.quic.configuration import QuicConfiguration
from quic_common import ALPN, PORT, generate_self_signed_certificate

HOST = "::"  # dual-stack: accepts IPv6 and IPv4 clients


async def handle_stream(reader, writer):
    """Serve one QUIC stream: read it to its end, answer, close it."""
    # A QUIC stream has an explicit end, so no delimiter is needed: read()
    # returns once the peer has finished writing. In TCP the newline had to
    # do that job, because a TCP connection is one undivided byte stream.
    data = await reader.read()
    sentence = data.decode("utf-8", errors="replace").rstrip("\n")
    print(f"received: {sentence!r}", flush=True)

    writer.write(sentence.upper().encode("utf-8"))
    writer.write_eof()  # ends this stream, not the connection


def stream_handler(reader, writer):
    """Called by aioquic for every new stream; must not block."""
    asyncio.ensure_future(handle_stream(reader, writer))


async def serve_forever(port):
    configuration = QuicConfiguration(is_client=False, alpn_protocols=ALPN)
    certificate, private_key = generate_self_signed_certificate()
    configuration.certificate = certificate
    configuration.private_key = private_key

    await serve(HOST, port, configuration=configuration, stream_handler=stream_handler)
    print(f"server listening on UDP port {port}", flush=True)
    print("certificate: freshly generated, self-signed", flush=True)

    await asyncio.Future()  # run until interrupted


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else PORT
    try:
        asyncio.run(serve_forever(port))
    except KeyboardInterrupt:
        print("\nserver stopped")


if __name__ == "__main__":
    main()
