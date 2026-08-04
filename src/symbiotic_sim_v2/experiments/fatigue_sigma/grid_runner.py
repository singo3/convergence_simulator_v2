"""Deterministic CPU-sequential paired condition-grid execution."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from symbiotic_sim_v2.runtime.experimental_multi_session.runner import (
    FatigueSigmaSingleConditionRunner,
)
from symbiotic_sim_v2.virtual_user.stationary_landscape_v2 import (
    stationary_user_type_profile_v2,
)

from .aggregation import (
    FatigueSigmaConditionSummary,
    FatigueSigmaReplicateResult,
    aggregate_condition,
    replicate_result_from_single,
)
from .canonical import canonical_digest
from .condition import FatigueSigmaCondition, FatigueSigmaGridConfig
from .config import (
    FATIGUE_SIGMA_GRID_SUMMARY_SCHEMA_VERSION,
    PROJECT_VERSION,
)
from .manifest import FatigueSigmaExperimentManifest
from .replicate_seed import paired_replicate_master_seed

type CancelCheck = Callable[[], bool]
type ProgressCallback = Callable[[dict[str, Any]], None]
type RunnerFactory = Callable[..., FatigueSigmaSingleConditionRunner]


@dataclass(frozen=True, slots=True)
class FatigueSigmaGridSummary:
    project_version: str
    experiment_manifest: dict[str, Any]
    user_type: dict[str, Any]
    fatigue_values: tuple[float, ...]
    sigma_values: tuple[float, ...]
    maximum_sessions: int
    replicate_count: int
    total_planned_session_runs: int
    completed_session_runs: int
    completed_conditions: int
    failed_conditions: int
    cancelled: bool
    paired_replicate_seeds: tuple[int, ...]
    replicate_results: tuple[FatigueSigmaReplicateResult, ...]
    condition_summaries: tuple[FatigueSigmaConditionSummary, ...]
    experiment_conditions: tuple[Mapping[str, Any], ...]
    fatigue_trajectory: tuple[Mapping[str, Any], ...]
    sigma_trajectory: tuple[Mapping[str, Any], ...]
    session_pattern_trajectory: tuple[Mapping[str, Any], ...]
    structured_convergence_history: tuple[Mapping[str, Any], ...]
    reference_arm_metadata: dict[str, Any]
    grid_digests: dict[str, str]
    schema_version: str = FATIGUE_SIGMA_GRID_SUMMARY_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_version": self.project_version,
            "experiment_manifest": dict(self.experiment_manifest),
            "user_type": dict(self.user_type),
            "fatigue_values": list(self.fatigue_values),
            "sigma_values": list(self.sigma_values),
            "sessions": self.maximum_sessions,
            "replicates": self.replicate_count,
            "total_planned_session_runs": self.total_planned_session_runs,
            "completed_session_runs": self.completed_session_runs,
            "completed_conditions": self.completed_conditions,
            "failed_conditions": self.failed_conditions,
            "cancelled": self.cancelled,
            "paired_replicate_seeds": list(self.paired_replicate_seeds),
            "replicate_results": [
                item.to_dict() for item in self.replicate_results
            ],
            "per_condition_summaries": [
                item.to_dict() for item in self.condition_summaries
            ],
            "export_record_counts": {
                "experiment_conditions": len(self.experiment_conditions),
                "fatigue_trajectory": len(self.fatigue_trajectory),
                "sigma_trajectory": len(self.sigma_trajectory),
                "session_pattern_trajectory": len(
                    self.session_pattern_trajectory
                ),
                "structured_convergence_history": len(
                    self.structured_convergence_history
                ),
            },
            "reference_arm_metadata": dict(self.reference_arm_metadata),
            "policy_flags": {
                "stationary_preference": True,
                "moving_preference": False,
                "unselected_full_recovery": True,
                "convergence_is_diagnostic_only": True,
                "exploration_continues_after_convergence": True,
                "p_explore_modified": False,
                "epsilon_accept_modified": False,
                "q_coefficients_modified": False,
                "v2_reference_arm_available": True,
                "formal_spec_adoption": False,
                "Monte_Carlo": False,
            },
            "grid_digests": dict(self.grid_digests),
            "schema_version": self.schema_version,
        }


class FatigueSigmaGridRunner:
    """Use fresh state/component/engine objects for every paired replicate."""

    def __init__(
        self,
        config: FatigueSigmaGridConfig | None = None,
        *,
        runner_factory: RunnerFactory = FatigueSigmaSingleConditionRunner,
        condition_order: Sequence[tuple[float, float]] | None = None,
    ) -> None:
        self._config = config or FatigueSigmaGridConfig()
        if not isinstance(self._config, FatigueSigmaGridConfig):
            raise TypeError("config must be a FatigueSigmaGridConfig")
        if not callable(runner_factory):
            raise TypeError("runner_factory must be callable")
        canonical = tuple(
            (fatigue, sigma)
            for fatigue in self._config.fatigue_targets
            for sigma in self._config.sigma_multipliers
        )
        if condition_order is not None:
            supplied = tuple(condition_order)
            if len(supplied) != len(set(supplied)) or set(supplied) != set(canonical):
                raise ValueError("condition_order must contain the exact grid once")
        # Output and execution are canonical even if a caller supplied another order.
        self._condition_order = tuple(sorted(canonical))
        self._runner_factory = runner_factory
        self._latest_summary: FatigueSigmaGridSummary | None = None

    @property
    def config(self) -> FatigueSigmaGridConfig:
        return self._config

    @property
    def latest_summary(self) -> FatigueSigmaGridSummary | None:
        return self._latest_summary

    def run(
        self,
        *,
        cancel_check: CancelCheck | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> FatigueSigmaGridSummary:
        if cancel_check is not None and not callable(cancel_check):
            raise TypeError("cancel_check must be callable")
        if progress_callback is not None and not callable(progress_callback):
            raise TypeError("progress_callback must be callable")
        paired_seeds = tuple(
            paired_replicate_master_seed(
                self._config.base_master_seed,
                replicate_index,
            )
            for replicate_index in range(self._config.replicate_count)
        )
        results: list[FatigueSigmaReplicateResult] = []
        summaries: list[FatigueSigmaConditionSummary] = []
        experiment_conditions: list[Mapping[str, Any]] = []
        fatigue_trajectory: list[Mapping[str, Any]] = []
        sigma_trajectory: list[Mapping[str, Any]] = []
        session_pattern_trajectory: list[Mapping[str, Any]] = []
        structured_convergence_history: list[Mapping[str, Any]] = []
        completed_session_runs = 0
        completed_conditions = failed_conditions = 0
        cancelled = False
        for fatigue, sigma in self._condition_order:
            condition_results: list[FatigueSigmaReplicateResult] = []
            condition_cancelled = False
            for replicate_index, replicate_seed in enumerate(paired_seeds):
                if cancel_check is not None and cancel_check():
                    cancelled = condition_cancelled = True
                    break
                condition = FatigueSigmaCondition.create(
                    user_type_id=self._config.user_type_id,
                    selected_session_fatigue_target=fatigue,
                    sigma_multiplier=sigma,
                    maximum_sessions=self._config.maximum_sessions,
                    master_seed=replicate_seed,
                )
                runner = self._runner_factory(condition, compare_reference_arm=False)
                partial_cancelled = False
                while runner.can_run_next_session:
                    if cancel_check is not None and cancel_check():
                        cancelled = condition_cancelled = partial_cancelled = True
                        break
                    runner.run_next_session()
                    completed_session_runs += 1
                    if progress_callback is not None:
                        progress_callback(
                            {
                                "completed_session_runs": completed_session_runs,
                                "total_planned_session_runs": (
                                    self._config.total_planned_session_runs
                                ),
                                "message": "session_boundary",
                                "condition_id": condition.condition_id,
                                "replicate_index": replicate_index,
                                "session_index": len(runner.session_outcomes()) - 1,
                            }
                        )
                    if runner.stopped_on_error:
                        break
                if partial_cancelled:
                    break
                single_result = runner.result()
                replicate = replicate_result_from_single(
                    single_result,
                    replicate_index=replicate_index,
                    replicate_master_seed=replicate_seed,
                )
                condition_results.append(replicate)
                results.append(replicate)
                if replicate.completed:
                    annotation = {
                        "condition_id": condition.condition_id,
                        "replicate_index": replicate_index,
                        "replicate_master_seed": replicate_seed,
                    }
                    experiment_conditions.append(
                        {
                            **condition.to_dict(),
                            **annotation,
                        }
                    )
                    for source, destination in (
                        (single_result.fatigue_trajectory, fatigue_trajectory),
                        (single_result.sigma_trajectory, sigma_trajectory),
                        (
                            single_result.session_pattern_trajectory,
                            session_pattern_trajectory,
                        ),
                        (
                            single_result.structured_convergence_history,
                            structured_convergence_history,
                        ),
                    ):
                        destination.extend(
                            {
                                **dict(row),
                                **annotation,
                            }
                            for row in source
                        )
                if progress_callback is not None:
                    progress_callback(
                        {
                            "completed_session_runs": completed_session_runs,
                            "total_planned_session_runs": (
                                self._config.total_planned_session_runs
                            ),
                            "message": "replicate_boundary",
                            "condition_id": condition.condition_id,
                            "replicate_index": replicate_index,
                            "session_index": None,
                        }
                    )
            if condition_cancelled:
                break
            summary = aggregate_condition(tuple(condition_results))
            summaries.append(summary)
            if (
                len(condition_results) == self._config.replicate_count
                and all(item.completed for item in condition_results)
            ):
                completed_conditions += 1
            else:
                failed_conditions += 1
            if progress_callback is not None:
                progress_callback(
                    {
                        "completed_session_runs": completed_session_runs,
                        "total_planned_session_runs": (
                            self._config.total_planned_session_runs
                        ),
                        "message": "condition_boundary",
                        "condition_id": summary.condition_id,
                        "replicate_index": None,
                        "session_index": None,
                    }
                )
        manifest = FatigueSigmaExperimentManifest().to_dict()
        summary_payloads = tuple(item.to_dict() for item in summaries)
        replicate_payloads = tuple(item.to_dict() for item in results)
        condition_payloads = tuple(dict(item) for item in experiment_conditions)
        fatigue_payloads = tuple(dict(item) for item in fatigue_trajectory)
        sigma_payloads = tuple(dict(item) for item in sigma_trajectory)
        pattern_payloads = tuple(
            dict(item) for item in session_pattern_trajectory
        )
        structured_payloads = tuple(
            dict(item) for item in structured_convergence_history
        )
        export_digests = {
            "experiment_condition_digest": canonical_digest(condition_payloads),
            "fatigue_trajectory_digest": canonical_digest(fatigue_payloads),
            "sigma_trajectory_digest": canonical_digest(sigma_payloads),
            "structured_convergence_digest": canonical_digest(
                structured_payloads
            ),
        }
        digest_payload = {
            "config": self._config.to_dict(),
            "paired_replicate_seeds": paired_seeds,
            "replicates": replicate_payloads,
            "conditions": summary_payloads,
            "export_digests": export_digests,
            "session_pattern_trajectory_digest": canonical_digest(
                pattern_payloads
            ),
            "cancelled": cancelled,
        }
        grid_digests = {
            **export_digests,
            "replicate_result_digest": canonical_digest(replicate_payloads),
            "condition_summary_digest": canonical_digest(summary_payloads),
            "experiment_manifest_digest": manifest["experiment_manifest_digest"],
            "grid_summary_digest": canonical_digest(digest_payload),
        }
        summary = FatigueSigmaGridSummary(
            project_version=PROJECT_VERSION,
            experiment_manifest=manifest,
            user_type=stationary_user_type_profile_v2(
                self._config.user_type_id
            ).to_dict(),
            fatigue_values=self._config.fatigue_targets,
            sigma_values=self._config.sigma_multipliers,
            maximum_sessions=self._config.maximum_sessions,
            replicate_count=self._config.replicate_count,
            total_planned_session_runs=self._config.total_planned_session_runs,
            completed_session_runs=completed_session_runs,
            completed_conditions=completed_conditions,
            failed_conditions=failed_conditions,
            cancelled=cancelled,
            paired_replicate_seeds=paired_seeds,
            replicate_results=tuple(results),
            condition_summaries=tuple(summaries),
            experiment_conditions=condition_payloads,
            fatigue_trajectory=fatigue_payloads,
            sigma_trajectory=sigma_payloads,
            session_pattern_trajectory=pattern_payloads,
            structured_convergence_history=structured_payloads,
            reference_arm_metadata={
                "available": True,
                "arm_name": "v2_coefficient_reference_arm",
                "experimental_full_recovery_is_not_reference_policy": True,
            },
            grid_digests=grid_digests,
        )
        self._latest_summary = summary
        return summary


__all__ = [
    "CancelCheck",
    "FatigueSigmaGridRunner",
    "FatigueSigmaGridSummary",
    "ProgressCallback",
    "RunnerFactory",
]
