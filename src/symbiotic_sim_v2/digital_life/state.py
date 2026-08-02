"""Internal mutable state for the Stage 5A first-round component."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class DigitalLifeState:
    e: float
    q: float
    k_anchor: tuple[float, float, float, float]
    k_current: tuple[float, float, float, float]
    n_baseline_session: float | None
    n_current: float | None
    nd: float
    w: float
    p: float
    v: float | None
    b: tuple[float, float, float, float]
    tau: float | None
    g_status: str
    last_processed_signal_index: int | None
    last_processed_evaluation_revision: int
    baseline_initialized: bool
    new_valid_evaluation_count: int
    second_round_connected: bool
    touch_dispatched_count: int
