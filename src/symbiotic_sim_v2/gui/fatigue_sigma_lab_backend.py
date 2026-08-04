"""Concrete adapter from Qt worker operations to the Stage 8A.1 core."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from symbiotic_sim_v2.experiments.fatigue_sigma.condition import (
    FatigueSigmaCondition,
    FatigueSigmaGridConfig,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.exports import (
    export_grid_csv,
    export_single_condition_csv,
)
from symbiotic_sim_v2.experiments.fatigue_sigma.grid_runner import (
    FatigueSigmaGridRunner,
)
from symbiotic_sim_v2.runtime.experimental_multi_session import (
    FatigueSigmaSingleConditionRunner,
    export_experiment_state_file,
    load_experiment_state_file,
)


def _setting(settings: Mapping[str, object], name: str) -> object:
    try:
        return settings[name]
    except KeyError as exc:
        raise ValueError(f"missing Stage 8A.1 GUI setting: {name}") from exc


def _boolean_setting(settings: Mapping[str, object], name: str) -> bool:
    value = _setting(settings, name)
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be boolean")
    return value


def _condition(settings: Mapping[str, object]) -> FatigueSigmaCondition:
    return FatigueSigmaCondition.create(
        user_type_id=_setting(settings, "user_type_id"),  # type: ignore[arg-type]
        selected_session_fatigue_target=_setting(
            settings, "selected_session_fatigue_target"
        ),  # type: ignore[arg-type]
        sigma_multiplier=_setting(settings, "sigma_multiplier"),  # type: ignore[arg-type]
        maximum_sessions=_setting(settings, "maximum_sessions"),  # type: ignore[arg-type]
        master_seed=_setting(settings, "master_seed"),  # type: ignore[arg-type]
    )


def _grid_config(settings: Mapping[str, object]) -> FatigueSigmaGridConfig:
    return FatigueSigmaGridConfig(
        user_type_id=_setting(settings, "user_type_id"),  # type: ignore[arg-type]
        fatigue_targets=_setting(settings, "fatigue_targets"),  # type: ignore[arg-type]
        sigma_multipliers=_setting(settings, "sigma_multipliers"),  # type: ignore[arg-type]
        maximum_sessions=_setting(settings, "maximum_sessions"),  # type: ignore[arg-type]
        replicate_count=_setting(settings, "replicate_count"),  # type: ignore[arg-type]
        base_master_seed=_setting(settings, "base_master_seed"),  # type: ignore[arg-type]
    )


class CoreFatigueSigmaLabBackend:
    """Keep mutable orchestration outside Qt widgets and calculations."""

    def __init__(self) -> None:
        self._single_runner: FatigueSigmaSingleConditionRunner | None = None
        self._grid_summary = None

    def create_single_operation(
        self,
        action: str,
        settings: Mapping[str, object],
    ):
        if action not in {"next_session", "run_all", "compare_reference"}:
            raise ValueError("unknown single-condition operation")
        condition = _condition(settings)
        compare = _boolean_setting(settings, "compare_reference_arm")
        if action == "compare_reference":
            compare = True

        def operation(progress, control):
            runner = self._ensure_runner(
                condition,
                compare_reference=compare,
                force_new=action == "compare_reference",
            )
            if action == "next_session":
                if not control.cancel_requested and runner.can_run_next_session:
                    runner.run_next_session()
                    progress(self._single_progress(runner, "session_boundary"))
            else:
                while runner.can_run_next_session and not control.cancel_requested:
                    runner.run_next_session()
                    progress(self._single_progress(runner, "session_boundary"))
                    if control.pause_requested or runner.stopped_on_error:
                        break
            return runner.result()

        return operation

    def create_grid_operation(self, settings: Mapping[str, object]):
        config = _grid_config(settings)

        def operation(progress, control):
            grid = FatigueSigmaGridRunner(config)
            self._grid_summary = grid.run(
                cancel_check=lambda: control.cancel_requested,
                progress_callback=progress,
            )
            return self._grid_summary

        return operation

    def reset_single(self, settings: Mapping[str, object]):
        condition = _condition(settings)
        compare = _boolean_setting(settings, "compare_reference_arm")
        self._single_runner = FatigueSigmaSingleConditionRunner(
            condition,
            compare_reference_arm=compare,
        )
        return self._single_runner.result()

    def save_single_state(self, path: object) -> None:
        if self._single_runner is None:
            raise RuntimeError("no Stage 8A.1 single-condition state exists")
        export_experiment_state_file(Path(path), self._single_runner.state())

    def load_single_state(self, path: object):
        state = load_experiment_state_file(Path(path))
        self._single_runner = FatigueSigmaSingleConditionRunner(
            resume_state=state,
            compare_reference_arm=state.reference_arm_enabled,
        )
        return self._single_runner.result()

    def export_csv(self, path: object) -> None:
        directory = Path(path)
        if self._single_runner is not None:
            export_single_condition_csv(directory, self._single_runner.result())
            return
        if self._grid_summary is not None:
            export_grid_csv(directory, self._grid_summary)
            return
        raise RuntimeError("no Stage 8A.1 result exists")

    def current_simulation(self):
        return (
            None
            if self._single_runner is None
            else self._single_runner.current_simulation
        )

    def _ensure_runner(
        self,
        condition: FatigueSigmaCondition,
        *,
        compare_reference: bool,
        force_new: bool,
    ) -> FatigueSigmaSingleConditionRunner:
        current = self._single_runner
        settings_changed = current is not None and (
            current.condition != condition
            or current.compare_reference_arm != compare_reference
        )
        if (
            current is not None
            and current.session_outcomes()
            and settings_changed
            and not force_new
        ):
            raise RuntimeError(
                "Stage 8A.1 settings can change only after an explicit reset"
            )
        if (
            force_new
            or current is None
            or settings_changed
        ):
            current = FatigueSigmaSingleConditionRunner(
                condition,
                compare_reference_arm=compare_reference,
            )
            self._single_runner = current
        return current

    @staticmethod
    def _single_progress(
        runner: FatigueSigmaSingleConditionRunner,
        message: str,
    ) -> dict[str, Any]:
        return {
            "sessions_completed": len(runner.session_outcomes()),
            "completed": len(runner.session_outcomes()),
            "maximum_sessions": runner.condition.maximum_sessions,
            "total": runner.condition.maximum_sessions,
            "message": message,
        }


__all__ = ["CoreFatigueSigmaLabBackend"]
