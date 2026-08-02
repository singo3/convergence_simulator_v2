"""Normative deterministic Hash01 mapping."""

from __future__ import annotations

import hashlib

HASH01_DENOMINATOR = (1 << 48) - 1


def hash01(*parts: object) -> float:
    """Map colon-joined string representations to the closed unit interval."""

    if not parts:
        raise ValueError("Hash01 requires at least one argument")
    joined = ":".join(str(part) for part in parts).encode("utf-8")
    digest = hashlib.sha256(joined).digest()
    numerator = int.from_bytes(digest[:6], byteorder="big", signed=False)
    return numerator / HASH01_DENOMINATOR
