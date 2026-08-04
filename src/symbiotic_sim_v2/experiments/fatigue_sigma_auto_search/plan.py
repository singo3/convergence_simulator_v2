"""Deterministic smoke/quick/standard/robust coarse-refine-confirm plans."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, Decimal
from typing import Any

from .config import SEARCH_PLAN_SCHEMA_VERSION, AutoSearchConfig

FATIGUE_MIN = Decimal("0.000000")
FATIGUE_MAX = Decimal("0.200000")
SIGMA_MIN = Decimal("0.250000")
SIGMA_MAX = Decimal("1.500000")
DECIMAL_QUANTUM = Decimal("0.000001")


def canonical_number(value: float | str | Decimal) -> float:
    """Normalize one search-axis number without clipping it."""

    decimal = Decimal(str(value)).quantize(DECIMAL_QUANTUM, rounding=ROUND_HALF_EVEN)
    return float(decimal)


@dataclass(frozen=True, slots=True, order=True)
class ConditionPoint:
    selected_session_fatigue_target: float
    sigma_multiplier: float

    def __post_init__(self) -> None:
        fatigue = canonical_number(self.selected_session_fatigue_target)
        sigma = canonical_number(self.sigma_multiplier)
        if not float(FATIGUE_MIN) <= fatigue <= float(FATIGUE_MAX):
            raise ValueError("fatigue target is outside [0, 0.20]")
        if not float(SIGMA_MIN) <= sigma <= float(SIGMA_MAX):
            raise ValueError("sigma multiplier is outside [0.25, 1.50]")
        object.__setattr__(self, "selected_session_fatigue_target", fatigue)
        object.__setattr__(self, "sigma_multiplier", sigma)

    @property
    def condition_key(self) -> str:
        return (
            f"fatigue_{self.selected_session_fatigue_target:.6f}__sigma_{self.sigma_multiplier:.6f}"
        )

    def to_dict(self) -> dict[str, float | str]:
        return {
            "condition_key": self.condition_key,
            "selected_session_fatigue_target": (self.selected_session_fatigue_target),
            "sigma_multiplier": self.sigma_multiplier,
        }


@dataclass(frozen=True, slots=True)
class SearchPhasePlan:
    phase: str
    phase_number: int
    conditions: tuple[ConditionPoint, ...]
    maximum_condition_count: int
    maximum_sessions: int
    replicate_count: int
    user_type_ids: tuple[str, ...]

    @property
    def condition_count(self) -> int:
        return len(self.conditions)

    @property
    def planned_session_runs(self) -> int:
        return (
            self.condition_count
            * len(self.user_type_ids)
            * self.replicate_count
            * self.maximum_sessions
        )

    @property
    def maximum_planned_session_runs(self) -> int:
        return (
            self.maximum_condition_count
            * len(self.user_type_ids)
            * self.replicate_count
            * self.maximum_sessions
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "phase": self.phase,
            "phase_number": self.phase_number,
            "conditions": [item.to_dict() for item in self.conditions],
            "condition_count": self.condition_count,
            "maximum_condition_count": self.maximum_condition_count,
            "maximum_sessions": self.maximum_sessions,
            "replicate_count": self.replicate_count,
            "user_type_ids": list(self.user_type_ids),
            "planned_session_runs": self.planned_session_runs,
            "maximum_planned_session_runs": self.maximum_planned_session_runs,
        }

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> SearchPhasePlan:
        expected = {
            "phase",
            "phase_number",
            "conditions",
            "condition_count",
            "maximum_condition_count",
            "maximum_sessions",
            "replicate_count",
            "user_type_ids",
            "planned_session_runs",
            "maximum_planned_session_runs",
        }
        if set(values) != expected:
            raise ValueError("search phase plan fields differ")
        result = cls(
            phase=str(values["phase"]),
            phase_number=int(values["phase_number"]),
            conditions=tuple(
                ConditionPoint(
                    float(item["selected_session_fatigue_target"]),
                    float(item["sigma_multiplier"]),
                )
                for item in values["conditions"]
            ),
            maximum_condition_count=int(values["maximum_condition_count"]),
            maximum_sessions=int(values["maximum_sessions"]),
            replicate_count=int(values["replicate_count"]),
            user_type_ids=tuple(values["user_type_ids"]),
        )
        projection = result.to_dict()
        for field in (
            "condition_count",
            "planned_session_runs",
            "maximum_planned_session_runs",
        ):
            if values[field] != projection[field]:
                raise ValueError(f"search phase derived field differs: {field}")
        return result


@dataclass(frozen=True, slots=True)
class AutoSearchPlan:
    search_preset: str
    phases: tuple[SearchPhasePlan, ...]
    maximum_total_session_runs: int
    include_reference_arm: bool
    schema_version: str = SEARCH_PLAN_SCHEMA_VERSION

    @property
    def planned_session_runs(self) -> int:
        return sum(item.planned_session_runs for item in self.phases)

    @property
    def maximum_planned_session_runs(self) -> int:
        return sum(item.maximum_planned_session_runs for item in self.phases)

    @property
    def reference_session_runs(self) -> int:
        if not self.include_reference_arm:
            return 0
        # The reference cache key excludes condition and phase.  For equal
        # session counts only the widest replicate set is needed.
        by_sessions: dict[int, int] = {}
        for phase in self.phases:
            by_sessions[phase.maximum_sessions] = max(
                by_sessions.get(phase.maximum_sessions, 0),
                phase.replicate_count,
            )
        return sum(
            sessions * replicates * len(self.phases[0].user_type_ids)
            for sessions, replicates in by_sessions.items()
        )

    def with_phase_conditions(
        self,
        phase_name: str,
        conditions: tuple[ConditionPoint, ...],
    ) -> AutoSearchPlan:
        updated = tuple(
            SearchPhasePlan(
                phase=item.phase,
                phase_number=item.phase_number,
                conditions=conditions if item.phase == phase_name else item.conditions,
                maximum_condition_count=item.maximum_condition_count,
                maximum_sessions=item.maximum_sessions,
                replicate_count=item.replicate_count,
                user_type_ids=item.user_type_ids,
            )
            for item in self.phases
        )
        selected = next(item for item in updated if item.phase == phase_name)
        if selected.condition_count > selected.maximum_condition_count:
            raise ValueError(
                f"{phase_name} has {selected.condition_count} conditions; "
                f"maximum is {selected.maximum_condition_count}"
            )
        return AutoSearchPlan(
            search_preset=self.search_preset,
            phases=updated,
            maximum_total_session_runs=self.maximum_total_session_runs,
            include_reference_arm=self.include_reference_arm,
        )

    def phase(self, name: str) -> SearchPhasePlan:
        try:
            return next(item for item in self.phases if item.phase == name)
        except StopIteration as exc:
            raise KeyError(name) from exc

    def to_dict(self) -> dict[str, Any]:
        return {
            "search_preset": self.search_preset,
            "phases": [item.to_dict() for item in self.phases],
            "planned_session_runs": self.planned_session_runs,
            "maximum_planned_session_runs": self.maximum_planned_session_runs,
            "reference_session_runs": self.reference_session_runs,
            "maximum_total_session_runs": self.maximum_total_session_runs,
            "include_reference_arm": self.include_reference_arm,
            "budget_includes_reference_cache_runs": False,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_dict(cls, values: dict[str, Any]) -> AutoSearchPlan:
        expected = {
            "search_preset",
            "phases",
            "planned_session_runs",
            "maximum_planned_session_runs",
            "reference_session_runs",
            "maximum_total_session_runs",
            "include_reference_arm",
            "budget_includes_reference_cache_runs",
            "schema_version",
            "phase_selection_history",
        }
        required = expected - {"phase_selection_history"}
        if not required <= set(values) or set(values) - expected:
            raise ValueError("search plan fields differ")
        if values.get("schema_version") != SEARCH_PLAN_SCHEMA_VERSION:
            raise ValueError("search plan schema mismatch")
        if not isinstance(values.get("include_reference_arm"), bool):
            raise TypeError("include_reference_arm must be boolean")
        if values.get("budget_includes_reference_cache_runs") is not False:
            raise ValueError("search plan budget policy mismatch")
        result = cls(
            search_preset=str(values["search_preset"]),
            phases=tuple(SearchPhasePlan.from_dict(item) for item in values["phases"]),
            maximum_total_session_runs=int(values["maximum_total_session_runs"]),
            include_reference_arm=values["include_reference_arm"],
        )
        projection = result.to_dict()
        for field in (
            "planned_session_runs",
            "maximum_planned_session_runs",
            "reference_session_runs",
        ):
            if values[field] != projection[field]:
                raise ValueError(f"search plan derived field differs: {field}")
        return result


def _grid(fatigue: tuple[float, ...], sigma: tuple[float, ...]) -> tuple[ConditionPoint, ...]:
    return tuple(ConditionPoint(f, s) for f in fatigue for s in sigma)


def _preset_phases(config: AutoSearchConfig) -> tuple[SearchPhasePlan, ...]:
    users = config.user_type_ids
    if config.search_preset == "smoke":
        return (
            SearchPhasePlan(
                "coarse",
                1,
                _grid((0.03, 0.08), (0.75, 1.25)),
                4,
                4,
                1,
                users,
            ),
        )
    if config.search_preset == "quick":
        return (
            SearchPhasePlan(
                "coarse",
                1,
                _grid((0.03, 0.08, 0.15), (0.50, 1.00, 1.50)),
                9,
                12,
                2,
                users,
            ),
        )
    coarse_replicates = 3 if config.search_preset == "standard" else 5
    refine_conditions = 12 if config.search_preset == "standard" else 18
    refine_sessions = 24 if config.search_preset == "standard" else 60
    refine_replicates = 5 if config.search_preset == "standard" else 10
    confirm_conditions = 3 if config.search_preset == "standard" else 5
    confirm_replicates = 10 if config.search_preset == "standard" else 20
    phases = [
        SearchPhasePlan(
            "coarse",
            1,
            _grid(
                (0.00, 0.03, 0.05, 0.08, 0.10, 0.15),
                (0.50, 0.75, 1.00, 1.25, 1.50),
            ),
            30,
            24,
            coarse_replicates,
            users,
        )
    ]
    if config.stop_after_phase in {"refine", "confirm"}:
        phases.append(
            SearchPhasePlan(
                "refine",
                2,
                (),
                refine_conditions,
                refine_sessions,
                refine_replicates,
                users,
            )
        )
    if config.stop_after_phase == "confirm":
        phases.append(
            SearchPhasePlan(
                "confirm",
                3,
                (),
                confirm_conditions,
                60,
                confirm_replicates,
                users,
            )
        )
    return tuple(phases)


def build_search_plan(config: AutoSearchConfig) -> AutoSearchPlan:
    if not isinstance(config, AutoSearchConfig):
        raise TypeError("config must be AutoSearchConfig")
    plan = AutoSearchPlan(
        search_preset=config.search_preset,
        phases=_preset_phases(config),
        maximum_total_session_runs=config.maximum_total_session_runs,
        include_reference_arm=config.include_reference_arm,
    )
    if plan.maximum_planned_session_runs > config.maximum_total_session_runs:
        raise ValueError(
            "planned session runs exceed the configured maximum: "
            f"{plan.maximum_planned_session_runs} > "
            f"{config.maximum_total_session_runs}"
        )
    return plan


def local_neighborhood(
    seeds: tuple[ConditionPoint, ...],
    *,
    maximum_conditions: int,
) -> tuple[ConditionPoint, ...]:
    """Build a bounded, canonical, de-duplicated local neighborhood."""

    candidates: set[ConditionPoint] = set()
    for seed in seeds:
        base_f = Decimal(str(seed.selected_session_fatigue_target))
        base_s = Decimal(str(seed.sigma_multiplier))
        for f_delta in (Decimal("-0.015"), Decimal("0"), Decimal("0.015")):
            fatigue = base_f + f_delta
            if not FATIGUE_MIN <= fatigue <= FATIGUE_MAX:
                continue
            for s_delta in (Decimal("-0.125"), Decimal("0"), Decimal("0.125")):
                sigma = base_s + s_delta
                if not SIGMA_MIN <= sigma <= SIGMA_MAX:
                    continue
                candidates.add(ConditionPoint(float(fatigue), float(sigma)))
    ordered = tuple(sorted(candidates))
    return ordered[:maximum_conditions]


__all__ = [
    "AutoSearchPlan",
    "ConditionPoint",
    "SearchPhasePlan",
    "build_search_plan",
    "canonical_number",
    "local_neighborhood",
]
