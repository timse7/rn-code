"""Shared pieces of the QUIC example: ALPN name and a throwaway certificate.

QUIC has no unencrypted mode. TLS 1.3 is part of the protocol, so a server
cannot start without a certificate and a key -- unlike the TCP and UDP
examples, which just bind a socket and go.

To keep the example self-contained, the server generates a fresh self-signed
certificate in memory every time it starts. Nothing is written to disk and no
private key is checked into this repository, which is exactly what you want
for a throwaway demo and exactly what you must not do in production.
"""

import datetime

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID

# Both endpoints must agree during the handshake on which application protocol
# runs on top of QUIC. Real ones here would be "h3" (HTTP/3) or "doq" (DNS).
ALPN = ["rn-echo"]

PORT = 4433  # the customary port for QUIC experiments


def generate_self_signed_certificate(common_name="localhost"):
    """Return a (certificate, private key) pair valid for one year."""
    # An elliptic-curve key takes a millisecond to generate; an RSA key of
    # comparable strength would take about a second on every server start.
    key = ec.generate_private_key(ec.SECP256R1())

    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.datetime.now(datetime.timezone.utc)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)  # self-signed: subject and issuer are the same
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName(common_name)]), critical=False
        )
        .sign(key, hashes.SHA256())
    )
    return certificate, key
