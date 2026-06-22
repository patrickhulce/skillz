"""Idiomatic Python wrapper over the native extension."""

from myplaceholder_project._myplaceholder_project import echo as _echo_native


def echo(data: bytes) -> bytes:
    """Return a copy of ``data`` (stub API — replace with real logic in Rust)."""
    if not isinstance(data, (bytes, bytearray)):
        raise TypeError("data must be bytes")
    return bytes(_echo_native(bytes(data)))
