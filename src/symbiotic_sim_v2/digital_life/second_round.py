"""Pure Stage 5B second-round decisions owned by one Digital Life."""

from __future__ import annotations

from dataclasses import dataclass

from symbiotic_sim_v2.digital_life.math import calculate_q_next


def _required_string(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")
    return value


def calculate_g(
    digital_life_id: object,
    qualification_holder_id: object | None,
) -> int:
    """Return binary G from this life's own ID comparison only."""

    own_id = _required_string("digital_life_id", digital_life_id)
    if qualification_holder_id is None:
        return 0
    holder_id = _required_string(
        "qualification_holder_id", qualification_holder_id
    )
    return int(own_id == holder_id)


@dataclass(frozen=True, slots=True)
class QUpdateDecision:
    q_after: float
    applied: bool
    skip_reason: str


def decide_q_update(
    *,
    q: object,
    w: object,
    g: object,
    evaluation_present: bool,
    is_new_valid_evaluation: bool,
    evaluation_kind: str | None,
    evaluation_is_valid: bool | None,
) -> QUpdateDecision:
    """Apply q only for a new valid bundle evaluation with local G equal to one."""

    if not isinstance(evaluation_present, bool):
        raise TypeError("evaluation_present must be boolean")
    if not isinstance(is_new_valid_evaluation, bool):
        raise TypeError("is_new_valid_evaluation must be boolean")
    if evaluation_is_valid is not None and not isinstance(evaluation_is_valid, bool):
        raise TypeError("evaluation_is_valid must be boolean or null")

    # calculate_q_next provides the strict finite [0,1] validation for q/w/G.
    unchanged = calculate_q_next(q, w, 0)
    candidate = calculate_q_next(q, w, g)
    if not evaluation_present:
        return QUpdateDecision(unchanged, False, "no_new_evaluation")
    if evaluation_is_valid is not True:
        return QUpdateDecision(unchanged, False, "evaluation_rejected")
    if evaluation_kind not in {"baseline", "bundle"}:
        raise ValueError("evaluation_kind must be baseline or bundle")
    if evaluation_kind == "baseline":
        return QUpdateDecision(
            unchanged,
            False,
            "baseline_not_intervention_evaluation",
        )
    if not is_new_valid_evaluation:
        return QUpdateDecision(unchanged, False, "no_new_evaluation")
    if g == 0:
        return QUpdateDecision(unchanged, False, "g_zero")
    return QUpdateDecision(candidate, True, "applied")
