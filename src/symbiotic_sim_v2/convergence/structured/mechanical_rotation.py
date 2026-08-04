"""Holder-sequence diagnostics for artificial rotation patterns."""

from __future__ import annotations

import math
import statistics
from collections import Counter
from collections.abc import Mapping, Sequence

from .config import StructuredConvergenceConfig
from .records import (
    EDrivenSwitchRecord,
    MechanicalRotationRecord,
    StructuredSessionObservation,
)


def _rate(numerator: int, denominator: int) -> float:
    return 0.0 if denominator == 0 else numerator / denominator


def _dominant_life(holders: tuple[str, ...]) -> str | None:
    if not holders:
        return None
    counts = Counter(holders)
    latest = {
        life_id: max(i for i, value in enumerate(holders) if value == life_id) for life_id in counts
    }
    return min(counts, key=lambda life_id: (-counts[life_id], -latest[life_id], life_id))


def evaluate_mechanical_rotation(
    valid_observations: tuple[StructuredSessionObservation, ...],
) -> MechanicalRotationRecord:
    holders = tuple(item.holder_id for item in valid_observations if item.holder_id is not None)
    switch_opportunities = max(0, len(holders) - 1)
    switch_count = sum(first != second for first, second in zip(holders, holders[1:], strict=False))
    triples = tuple(zip(holders, holders[1:], holders[2:], strict=False))
    distinct_count = sum(len({first, second, third}) == 3 for first, second, third in triples)
    immediate_return_count = sum(
        first == third and first != second for first, second, third in triples
    )
    quadruples = tuple(zip(holders, holders[1:], holders[2:], holders[3:], strict=False))
    cycle_count = sum(
        first == fourth and len({first, second, third}) == 3
        for first, second, third, fourth in quadruples
    )
    dominant = _dominant_life(holders)
    dominant_opportunities = dominant_returns = 0
    if dominant is not None:
        for position, holder in enumerate(holders[:-1]):
            if holder == dominant:
                continue
            dominant_opportunities += 1
            if holders[position + 1] == dominant:
                dominant_returns += 1
    prior_position: dict[str, int] = {}
    intervals: list[int] = []
    for position, holder in enumerate(holders):
        if holder in prior_position:
            intervals.append(position - prior_position[holder])
        prior_position[holder] = position
    return MechanicalRotationRecord(
        valid_session_count=len(holders),
        dominant_life_id=dominant,
        holder_switch_count=switch_count,
        holder_switch_opportunities=switch_opportunities,
        holder_switch_rate=_rate(switch_count, switch_opportunities),
        three_distinct_life_window_count=distinct_count,
        three_session_window_count=len(triples),
        three_distinct_life_window_rate=_rate(distinct_count, len(triples)),
        immediate_return_count=immediate_return_count,
        immediate_return_rate=_rate(immediate_return_count, len(triples)),
        three_life_cycle_count=cycle_count,
        four_session_window_count=len(quadruples),
        three_life_cycle_rate=_rate(cycle_count, len(quadruples)),
        dominant_life_return_count=dominant_returns,
        dominant_life_return_opportunities=dominant_opportunities,
        dominant_life_return_rate=_rate(dominant_returns, dominant_opportunities),
        mean_sessions_between_same_life_selections=(
            None if not intervals else statistics.fmean(intervals)
        ),
    )


def evaluate_e_driven_switches(
    session_snapshots: Sequence[object],
    config: StructuredConvergenceConfig | None = None,
) -> EDrivenSwitchRecord:
    """Join session-start E only in a separate non-convergence audit."""

    selected_config = StructuredConvergenceConfig() if config is None else config
    if isinstance(session_snapshots, (str, bytes)) or not isinstance(
        session_snapshots,
        Sequence,
    ):
        raise TypeError("session_snapshots must be a sequence")

    def read(snapshot: object, name: str) -> object:
        if isinstance(snapshot, Mapping):
            if name not in snapshot:
                raise ValueError(f"session snapshot is missing {name}")
            return snapshot[name]
        try:
            return getattr(snapshot, name)
        except AttributeError as exc:
            raise ValueError(f"session snapshot is missing {name}") from exc

    def start_e_by_life(snapshot: object) -> Mapping[object, object]:
        if isinstance(snapshot, Mapping) and "e_at_session_start_by_life" in snapshot:
            values = snapshot["e_at_session_start_by_life"]
        elif hasattr(snapshot, "e_at_session_start_by_life"):
            values = snapshot.e_at_session_start_by_life
        else:
            fatigue = read(snapshot, "fatigue_trajectory_by_life")
            if not isinstance(fatigue, Mapping):
                raise TypeError("fatigue_trajectory_by_life must be a mapping")
            values = {
                life_id: record["e_at_session_start"]
                for life_id, record in fatigue.items()
                if isinstance(record, Mapping) and "e_at_session_start" in record
            }
        if not isinstance(values, Mapping):
            raise TypeError("e_at_session_start_by_life must be a mapping")
        return values

    switches = evaluable = lower = 0
    advantages: list[float] = []
    values = tuple(session_snapshots)
    for previous, current in zip(values, values[1:], strict=False):
        previous_holder = read(previous, "holder_id")
        current_holder = read(current, "holder_id")
        if previous_holder is None or current_holder is None or previous_holder == current_holder:
            continue
        switches += 1
        start_e = start_e_by_life(current)
        if previous_holder not in start_e or current_holder not in start_e:
            continue
        outgoing_e = float(start_e[previous_holder])
        incoming_e = float(start_e[current_holder])
        if not math.isfinite(outgoing_e) or not math.isfinite(incoming_e):
            raise ValueError("session-start E values must be finite")
        evaluable += 1
        advantage = outgoing_e - incoming_e
        advantages.append(advantage)
        if advantage > 0.0:
            lower += 1
    rate = _rate(lower, evaluable)
    return EDrivenSwitchRecord(
        holder_switch_count=switches,
        evaluable_switch_count=evaluable,
        lower_incoming_e_switch_count=lower,
        lower_incoming_e_switch_rate=rate,
        mean_incoming_e_advantage=(None if not advantages else statistics.fmean(advantages)),
        e_driven_switch_warning=(
            evaluable >= selected_config.mechanical_warning_minimum_windows
            and rate >= selected_config.mechanical_warning_rate_threshold
        ),
    )


__all__ = ["evaluate_e_driven_switches", "evaluate_mechanical_rotation"]
