"""Generate a VAPID keypair.

    python -m app.vapid

Run once. The keys identify this server to the browsers' push services; rotating them
invalidates every existing subscription, so store them and do not regenerate casually.
"""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def main() -> None:
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_numbers = private_key.public_key().public_numbers()

    public_raw = (
        b"\x04"
        + public_numbers.x.to_bytes(32, "big")
        + public_numbers.y.to_bytes(32, "big")
    )
    private_raw = private_key.private_numbers().private_value.to_bytes(32, "big")

    print("VAPID_PUBLIC_KEY=" + _b64(public_raw))
    print("VAPID_PRIVATE_KEY=" + _b64(private_raw))
    print()
    print("Put both in the environment. The public key is also sent to the browser;")
    print("the private key never leaves the server.")
    # Silence the unused-import warning while keeping the dependency explicit.
    _ = serialization


if __name__ == "__main__":
    main()
