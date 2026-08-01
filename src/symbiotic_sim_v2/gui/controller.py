"""Qt controller translating wall-time UI activity into engine operations."""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtCore import QObject, Qt, QTimer, Signal, Slot

from symbiotic_sim_v2.domain.events import SimulationEvent
from symbiotic_sim_v2.simulation.clock import ClockState
from symbiotic_sim_v2.simulation.engine import EngineSnapshot, SimulationEngine
from symbiotic_sim_v2.simulation.time_utils import NANOSECONDS_PER_MICROSECOND

GUI_TIMER_INTERVAL_MS = 16
MAX_BATCH_EVENTS = 500
MAX_BATCH_WALL_BUDGET_MS = 8.0


class SpeedMode(StrEnum):
    """Wall-time execution policy selected by the user."""

    REALTIME = "realtime"
    X10 = "x10"
    X100 = "x100"
    MAXIMUM = "maximum"

    @property
    def label(self) -> str:
        """Return the Japanese GUI label."""

        return {
            SpeedMode.REALTIME: "等速",
            SpeedMode.X10: "10倍",
            SpeedMode.X100: "100倍",
            SpeedMode.MAXIMUM: "最速",
        }[self]

    @property
    def multiplier(self) -> int | None:
        """Return the integer multiplier, or ``None`` for batch mode."""

        return {
            SpeedMode.REALTIME: 1,
            SpeedMode.X10: 10,
            SpeedMode.X100: 100,
            SpeedMode.MAXIMUM: None,
        }[self]


@dataclass(frozen=True, slots=True)
class ControllerSnapshot:
    """Engine state plus wall-time diagnostics for one GUI refresh."""

    engine: EngineSnapshot
    speed_mode: SpeedMode
    real_elapsed_ns: int
    effective_speed: float | None


class SimulationController(QObject):
    """Keep QTimer/wall time outside the deterministic core engine."""

    snapshot_changed = Signal(object)
    events_executed = Signal(object)
    scenario_reset = Signal(object)
    speed_changed = Signal(object)

    def __init__(self, engine: SimulationEngine, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._engine = engine
        self._speed_mode = SpeedMode.REALTIME
        self._real_elapsed_ns = 0
        self._last_wall_ns: int | None = None
        self._scaled_remainder_ns = 0
        self._published_event_count = 0
        self._force_max_until_complete = False

        self._timer = QTimer(self)
        self._timer.setInterval(GUI_TIMER_INTERVAL_MS)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._on_timer)
        self._timer.start()

    @property
    def timer_active(self) -> bool:
        """Return whether the GUI wake-up timer is active."""

        return self._timer.isActive()

    @property
    def speed_mode(self) -> SpeedMode:
        """Return the currently selected wall-time policy."""

        return self._speed_mode

    def planned_events(self) -> tuple[SimulationEvent, ...]:
        """Expose planned markers to widgets without exposing the scheduler heap."""

        return self._engine.planned_events()

    def replace_engine(self, engine: SimulationEngine) -> None:
        """Replace a stopped scenario when pre-run settings are applied."""

        if self._engine.clock.state is not ClockState.STOPPED:
            raise RuntimeError("engine can only be replaced before simulation start")
        self._engine = engine
        self._real_elapsed_ns = 0
        self._last_wall_ns = None
        self._scaled_remainder_ns = 0
        self._published_event_count = 0
        self._force_max_until_complete = False
        self.scenario_reset.emit(self._engine.planned_events())
        self._publish()

    def current_snapshot(self) -> ControllerSnapshot:
        """Build the current engine-plus-diagnostics snapshot."""

        engine_snapshot = self._engine.snapshot()
        effective_speed = None
        if self._real_elapsed_ns > 0:
            effective_speed = (
                engine_snapshot.virtual_elapsed_us * NANOSECONDS_PER_MICROSECOND
            ) / self._real_elapsed_ns
        return ControllerSnapshot(
            engine=engine_snapshot,
            speed_mode=self._speed_mode,
            real_elapsed_ns=self._real_elapsed_ns,
            effective_speed=effective_speed,
        )

    @Slot()
    def start(self) -> None:
        """Start normal controller-driven execution."""

        self._engine.start()
        self._force_max_until_complete = False
        self._last_wall_ns = time.perf_counter_ns()
        self._publish()

    @Slot()
    def pause(self) -> None:
        """Account for the final wall interval, then pause the engine."""

        if self._engine.clock.state is not ClockState.RUNNING:
            return
        self._advance_for_wall_time(time.perf_counter_ns())
        if self._engine.clock.state is ClockState.RUNNING:
            self._engine.pause()
        self._last_wall_ns = None
        self._force_max_until_complete = False
        self._publish()

    @Slot()
    def resume(self) -> None:
        """Resume controller-driven execution with a fresh monotonic baseline."""

        self._engine.resume()
        self._last_wall_ns = time.perf_counter_ns()
        self._publish()

    @Slot()
    def reset(self) -> None:
        """Restore deterministic scenario state and clear wall-time diagnostics."""

        self._engine.reset()
        self._real_elapsed_ns = 0
        self._last_wall_ns = None
        self._scaled_remainder_ns = 0
        self._published_event_count = 0
        self._force_max_until_complete = False
        self.scenario_reset.emit(self._engine.planned_events())
        self._publish()

    @Slot()
    def step_one_second(self) -> None:
        """Perform one explicit virtual-second step."""

        self._engine.step_one_second()
        self._publish()

    @Slot()
    def step_one_event(self) -> None:
        """Perform one explicit event step."""

        self._engine.step_one_event()
        self._publish()

    @Slot()
    def run_to_end(self) -> None:
        """Request bounded maximum-speed batches until the scenario completes."""

        state = self._engine.clock.state
        if state is ClockState.COMPLETED:
            return
        if state is ClockState.STOPPED:
            self._engine.start()
        elif state is ClockState.PAUSED:
            self._engine.resume()
        self._force_max_until_complete = True
        self._last_wall_ns = time.perf_counter_ns()
        self._on_timer()

    @Slot(object)
    def set_speed(self, speed_mode: SpeedMode | str) -> None:
        """Change only the wall-time execution policy, never engine state/data."""

        selected = speed_mode if isinstance(speed_mode, SpeedMode) else SpeedMode(speed_mode)
        now_ns = time.perf_counter_ns()
        if self._engine.clock.state is ClockState.RUNNING:
            self._advance_for_wall_time(now_ns)
        self._speed_mode = selected
        self._last_wall_ns = now_ns if self._engine.clock.state is ClockState.RUNNING else None
        self.speed_changed.emit(selected)
        self._publish()

    @Slot()
    def shutdown(self) -> None:
        """Stop the GUI wake-up timer before its owning window is destroyed."""

        self._timer.stop()
        self._last_wall_ns = None

    @Slot()
    def _on_timer(self) -> None:
        if self._engine.clock.state is not ClockState.RUNNING:
            return
        self._advance_for_wall_time(time.perf_counter_ns())
        self._publish()

    def _advance_for_wall_time(self, now_ns: int) -> None:
        if self._last_wall_ns is None:
            self._last_wall_ns = now_ns
        delta_ns = max(0, now_ns - self._last_wall_ns)
        self._last_wall_ns = now_ns
        self._real_elapsed_ns += delta_ns

        if self._force_max_until_complete or self._speed_mode is SpeedMode.MAXIMUM:
            self._engine.run_max_batch(
                max_events=MAX_BATCH_EVENTS,
                wall_time_budget_ms=MAX_BATCH_WALL_BUDGET_MS,
            )
        else:
            multiplier = self._speed_mode.multiplier
            if multiplier is None:  # pragma: no cover - covered by the branch above
                raise RuntimeError("speed mode multiplier is unavailable")
            scaled_ns = delta_ns * multiplier + self._scaled_remainder_ns
            delta_us, self._scaled_remainder_ns = divmod(
                scaled_ns,
                NANOSECONDS_PER_MICROSECOND,
            )
            self._engine.advance_by_us(delta_us)

        if self._engine.clock.state is ClockState.COMPLETED:
            self._last_wall_ns = None
            self._force_max_until_complete = False

    def _publish(self) -> None:
        history = self._engine.executed_events()
        if len(history) > self._published_event_count:
            new_events = history[self._published_event_count :]
            self._published_event_count = len(history)
            self.events_executed.emit(new_events)
        self.snapshot_changed.emit(self.current_snapshot())
