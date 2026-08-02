"""Pure normative mappings used by the Stage 5A first-round model."""

from __future__ import annotations

import math
from collections.abc import Sequence

ETA_E = 1.0 - 0.85 ** (1.0 / 180.0)
RHO_E = 1.0 - 0.90 ** (1.0 / 180.0)


def _finite_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError(f"{name} must be finite")
    return converted


def _unit(name: str, value: object) -> float:
    converted = _finite_number(name, value)
    if not 0.0 <= converted <= 1.0:
        raise ValueError(f"{name} must be between 0 and 1")
    return converted


def _binary(name: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value not in (0, 1):
        raise ValueError(f"{name} must be 0 or 1")
    return value


def clip01(value: object) -> float:
    """Clip one finite, non-boolean numeric value into [0, 1]."""

    converted = _finite_number("value", value)
    return min(1.0, max(0.0, converted))


def calculate_nd(n_current: object, n_baseline_session: object, delta_n: object) -> float:
    """Map N to baseline-relative Nd using the fixed symmetric sensitivity span."""

    current = _unit("n_current", n_current)
    baseline = _unit("n_baseline_session", n_baseline_session)
    delta = _finite_number("delta_n", delta_n)
    if delta <= 0.0:
        raise ValueError("delta_n must be positive")
    return clip01(0.5 + (current - baseline) / (2.0 * delta))


def evaluate_w(nd: object) -> float:
    """Evaluate emotional weight W from Nd as a distinct MVP mapping."""

    return _unit("nd", nd)


def calculate_p(s: object, p_intrinsic: object) -> float:
    """Apply Phi_P: P = 1 - S * (1 - p_i)."""

    binary_s = _binary("s", s)
    intrinsic = _unit("p_intrinsic", p_intrinsic)
    return 1.0 - binary_s * (1.0 - intrinsic)


def calculate_v(n_current: object | None, q: object, e: object) -> float | None:
    """Calculate V, retaining unavailability before the first N exists."""

    if n_current is None:
        return None
    current = _unit("n_current", n_current)
    quality = _unit("q", q)
    experience = _unit("e", e)
    return clip01(((current + quality) / 2.0) * (1.0 - experience))


def intrinsic_b_mapping(
    k: Sequence[object],
    *,
    f_min: object,
    f_max: object,
    a_fixed: object,
    t_min: object,
    t_max: object,
    d_fixed: object,
) -> tuple[float, float, float, float]:
    """Apply element-wise Phi_B to k=[F,A,T,D] without W modulation."""

    if isinstance(k, (str, bytes)) or not isinstance(k, Sequence):
        raise TypeError("k must be a four-element sequence")
    if len(k) != 4:
        raise ValueError("k must contain four values")
    k_f, k_a, k_t, k_d = (_unit(f"k[{index}]", value) for index, value in enumerate(k))
    lower_f = _unit("f_min", f_min)
    upper_f = _unit("f_max", f_max)
    fixed_a = _unit("a_fixed", a_fixed)
    lower_t = _unit("t_min", t_min)
    upper_t = _unit("t_max", t_max)
    fixed_d = _unit("d_fixed", d_fixed)
    if lower_f >= upper_f:
        raise ValueError("f_min must be less than f_max")
    if lower_t >= upper_t:
        raise ValueError("t_min must be less than t_max")
    return (
        lower_f + (upper_f - lower_f) * k_f,
        fixed_a + (fixed_a - fixed_a) * k_a,
        lower_t + (upper_t - lower_t) * k_t,
        fixed_d + (fixed_d - fixed_d) * k_d,
    )


def calculate_tau(
    s: object,
    p: object,
    v: object | None,
    epsilon_tau: object,
    birth_phase: object,
) -> float | None:
    """Calculate logical arrival time; S=0 or unavailable V has no tau."""

    binary_s = _binary("s", s)
    activity_p = _unit("p", p)
    epsilon = _finite_number("epsilon_tau", epsilon_tau)
    phase = _unit("birth_phase", birth_phase)
    if epsilon <= 0.0:
        raise ValueError("epsilon_tau must be positive")
    if binary_s == 0 or v is None:
        return None
    activity_v = _unit("v", v)
    return clip01(activity_p / (activity_p + activity_v + epsilon) + phase)


def calculate_e_next(e: object, s: object, g: object) -> float:
    """Pure reference E update reserved for a later connected stage."""

    experience = _unit("e", e)
    binary_s = _binary("s", s)
    binary_g = _binary("g", g)
    sg = binary_s * binary_g
    return clip01(
        experience
        + ETA_E * sg * (1.0 - experience)
        - RHO_E * (1.0 - sg) * experience
    )


def w_plus(w: object) -> float:
    """Return the positive emotional contribution."""

    weight = _unit("w", w)
    return clip01((weight - 0.55) / 0.45)


def w_minus(w: object) -> float:
    """Return the negative emotional contribution."""

    weight = _unit("w", w)
    return clip01((0.45 - weight) / 0.45)


def calculate_q_next(q: object, w: object, g: object) -> float:
    """Pure reference q update reserved for a later new-evaluation contract."""

    quality = _unit("q", q)
    weight = _unit("w", w)
    binary_g = _binary("g", g)
    return clip01(
        quality
        + binary_g
        * (
            0.20 * w_plus(weight) * (1.0 - quality)
            - 0.20 * w_minus(weight) * quality
        )
    )
