"""Stateless SHA-256 named random values independent of call order and process."""

from __future__ import annotations

import hashlib
import math

_UINT64_RANGE = 2**64


def _digest(root_seed: int, stream_name: str, sample_index: int) -> bytes:
    if isinstance(root_seed, bool) or not isinstance(root_seed, int) or root_seed < 0:
        raise ValueError("root_seed must be a non-negative integer")
    if not isinstance(stream_name, str) or not stream_name:
        raise ValueError("stream_name must be a non-empty string")
    if isinstance(sample_index, bool) or not isinstance(sample_index, int) or sample_index < 0:
        raise ValueError("sample_index must be a non-negative integer")
    key = f"{root_seed}:{stream_name}:{sample_index}".encode("utf-8")  # noqa: UP012
    return hashlib.sha256(key).digest()


def _open_uniform(chunk: bytes) -> float:
    """Map 64 random bits to the open interval (0, 1)."""

    value = (int.from_bytes(chunk, byteorder="big", signed=False) + 0.5) / _UINT64_RANGE
    # A maximal 64-bit numerator can round to exactly 1.0 in binary64.
    return min(math.nextafter(1.0, 0.0), max(math.nextafter(0.0, 1.0), value))


def uniform01(root_seed: int, stream_name: str, sample_index: int) -> float:
    """Return a deterministic named uniform value strictly between zero and one."""

    return _open_uniform(_digest(root_seed, stream_name, sample_index)[0:8])


def standard_normal(root_seed: int, stream_name: str, sample_index: int) -> float:
    """Return a deterministic standard normal via a two-chunk Box-Muller transform."""

    digest = _digest(root_seed, stream_name, sample_index)
    uniform_a = _open_uniform(digest[0:8])
    uniform_b = _open_uniform(digest[8:16])
    return math.sqrt(-2.0 * math.log(uniform_a)) * math.cos(2.0 * math.pi * uniform_b)
