"""The single conversion and formatting boundary for simulation time."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

MICROSECONDS_PER_SECOND = 1_000_000
NANOSECONDS_PER_MICROSECOND = 1_000


def seconds_to_us(seconds: int | float | str | Decimal) -> int:
    """Convert exact decimal seconds to integer microseconds.

    Float inputs are first converted through their human-readable decimal string;
    values that cannot be represented as a whole microsecond are rejected.
    """

    if isinstance(seconds, bool):
        raise TypeError("seconds must be numeric, not bool")
    try:
        decimal_seconds = Decimal(str(seconds))
    except InvalidOperation as exc:
        raise ValueError("seconds must be a finite decimal value") from exc
    if not decimal_seconds.is_finite() or decimal_seconds < 0:
        raise ValueError("seconds must be finite and non-negative")
    microseconds = decimal_seconds * MICROSECONDS_PER_SECOND
    if microseconds != microseconds.to_integral_value():
        raise ValueError("seconds must resolve to a whole microsecond")
    return int(microseconds)


def us_to_seconds(microseconds: int) -> float:
    """Convert integer microseconds to seconds for display or plotting only."""

    _validate_us(microseconds)
    return microseconds / MICROSECONDS_PER_SECOND


def format_time_us(microseconds: int) -> str:
    """Format virtual time as ``HH:MM:SS.mmm`` without float arithmetic."""

    _validate_us(microseconds)
    total_milliseconds = microseconds // 1_000
    hours, remainder_ms = divmod(total_milliseconds, 3_600_000)
    minutes, remainder_ms = divmod(remainder_ms, 60_000)
    seconds, milliseconds = divmod(remainder_ms, 1_000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{milliseconds:03d}"


def indexed_local_time_to_global_us(
    index: int,
    segment_duration_us: int,
    local_time_us: int,
) -> int:
    """Translate one indexed segment's local integer time to aggregate time."""

    if isinstance(index, bool) or not isinstance(index, int):
        raise TypeError("index must be an integer")
    if index < 0:
        raise ValueError("index must be non-negative")
    duration = _validate_us(segment_duration_us)
    if duration == 0:
        raise ValueError("segment_duration_us must be positive")
    local = _validate_us(local_time_us)
    if local > duration:
        raise ValueError("local_time_us must not exceed segment_duration_us")
    return index * duration + local


def _validate_us(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("microseconds must be an integer")
    if value < 0:
        raise ValueError("microseconds must be non-negative")
    return value
