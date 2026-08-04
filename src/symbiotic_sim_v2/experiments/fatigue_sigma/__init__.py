"""Public Stage 8A.1 experiment configuration, runners, and exports.

The experiment package is also imported by the policy-owning runtime factory.
Resolve public objects lazily so importing one policy leaf never pulls the grid
runner back through the runtime package while that factory is still loading.
"""

from __future__ import annotations

from importlib import import_module

_LAZY_EXPORTS = {
    "FatigueSigmaCondition": (".condition", "FatigueSigmaCondition"),
    "FatigueSigmaConditionSummary": (
        ".aggregation",
        "FatigueSigmaConditionSummary",
    ),
    "FatigueSigmaExperimentManifest": (
        ".manifest",
        "FatigueSigmaExperimentManifest",
    ),
    "FatigueSigmaGridConfig": (".condition", "FatigueSigmaGridConfig"),
    "FatigueSigmaGridRunner": (".grid_runner", "FatigueSigmaGridRunner"),
    "FatigueSigmaGridSummary": (".grid_runner", "FatigueSigmaGridSummary"),
    "FatigueSigmaReplicateResult": (
        ".aggregation",
        "FatigueSigmaReplicateResult",
    ),
    "FatigueSigmaSingleConditionResult": (
        ".result",
        "FatigueSigmaSingleConditionResult",
    ),
    "ScaledReferenceSigmaPolicy": (
        ".sigma_policy",
        "ScaledReferenceSigmaPolicy",
    ),
    "ScaledSigmaDecision": (".sigma_policy", "ScaledSigmaDecision"),
    "SelectedSessionFatiguePolicy": (
        ".fatigue_policy",
        "SelectedSessionFatiguePolicy",
    ),
    "SessionEndFatigueDecision": (
        ".fatigue_policy",
        "SessionEndFatigueDecision",
    ),
    "aggregate_condition": (".aggregation", "aggregate_condition"),
    "build_single_condition_result": (
        ".result",
        "build_single_condition_result",
    ),
    "condition_id_for": (".condition", "condition_id_for"),
    "export_grid_csv": (".exports", "export_grid_csv"),
    "export_single_condition_csv": (
        ".exports",
        "export_single_condition_csv",
    ),
    "paired_physiology_root_seed": (
        ".replicate_seed",
        "paired_physiology_root_seed",
    ),
    "paired_replicate_master_seed": (
        ".replicate_seed",
        "paired_replicate_master_seed",
    ),
    "replicate_result_from_single": (
        ".aggregation",
        "replicate_result_from_single",
    ),
    "selected_session_eta": (".fatigue_policy", "selected_session_eta"),
}

__all__ = tuple(_LAZY_EXPORTS)


def __getattr__(name: str) -> object:
    """Load a public object without introducing package-initialization cycles."""

    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    value = getattr(import_module(module_name, __name__), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    """Expose lazy public names to interactive callers and documentation tools."""

    return sorted((*globals(), *__all__))
