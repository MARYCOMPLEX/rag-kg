"""Tiny ULID generator (Crockford-base32 26-char identifier).

Why not import `python-ulid` directly: keeping this helper inline removes
the runtime dependency, makes the unit test deterministic by injectable
clock, and the implementation is ~30 lines.

ULID layout:
- 48 bits: ms unix timestamp (10 chars in Crockford base32)
- 80 bits: cryptographic randomness (16 chars in Crockford base32)
- total 128 bits → 26 chars

ULIDs are sortable by timestamp prefix, exactly the property we want for
`tasks.task_id` so an ORDER BY on the PK is implicitly time-ordered.
"""

from __future__ import annotations

import secrets
import time
from collections.abc import Callable

# Crockford base32 alphabet (no I, L, O, U → 32 distinct characters).
_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_TIME_LEN = 10
_RANDOM_LEN = 16
ULID_LEN = _TIME_LEN + _RANDOM_LEN


def _encode_int(value: int, length: int) -> str:
    """Encode a non-negative integer in Crockford base32 with fixed length."""
    if value < 0:
        msg = "ULID component must be non-negative"
        raise ValueError(msg)
    digits: list[str] = []
    for _ in range(length):
        digits.append(_ALPHABET[value & 0x1F])
        value >>= 5
    if value:
        msg = "ULID component overflow"
        raise ValueError(msg)
    return "".join(reversed(digits))


def new_ulid(
    *,
    now_ms: Callable[[], int] = lambda: int(time.time() * 1000),
    randbits: Callable[[int], int] = secrets.randbits,
) -> str:
    """Return a freshly minted 26-char ULID string.

    Parameters are injectable for deterministic unit tests.
    """
    ts_ms = now_ms()
    rnd = randbits(80)
    return _encode_int(ts_ms, _TIME_LEN) + _encode_int(rnd, _RANDOM_LEN)


def is_ulid(value: str) -> bool:
    """Return True if `value` looks like a valid ULID (length + alphabet)."""
    if len(value) != ULID_LEN:
        return False
    return all(ch in _ALPHABET for ch in value)
