"""Immutable manifest separating the experimental arm from v2.0 adoption."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .canonical import canonical_digest
from .config import (
    BASE_PROFILE_VERSION,
    FATIGUE_EXPLORATION_CONVERGENCE_LAB_VERSION,
    FATIGUE_SIGMA_CONDITION_SCHEMA_VERSION,
    FATIGUE_SIGMA_CONDITION_SUMMARY_SCHEMA_VERSION,
    FATIGUE_SIGMA_EXPERIMENT_MANIFEST_SCHEMA_VERSION,
    FATIGUE_SIGMA_EXPERIMENT_PROFILE_VERSION,
    FATIGUE_SIGMA_GRID_SUMMARY_SCHEMA_VERSION,
    FATIGUE_SIGMA_REPLICATE_RESULT_SCHEMA_VERSION,
    FATIGUE_SIGMA_SESSION_OUTCOME_SCHEMA_VERSION,
    MODIFIED_FIELDS,
    PAIRED_REPLICATE_SEED_POLICY_VERSION,
    SCALED_REFERENCE_SIGMA_POLICY_VERSION,
    SELECTED_SESSION_FATIGUE_POLICY_VERSION,
    STRUCTURED_CONVERGENCE_DIAGNOSTICS_VERSION,
    UNCHANGED_REFERENCE_FIELDS,
    UNSELECTED_FULL_RECOVERY_POLICY_VERSION,
)


@dataclass(frozen=True, slots=True)
class FatigueSigmaExperimentManifest:
    lab_model_version: str = FATIGUE_EXPLORATION_CONVERGENCE_LAB_VERSION
    schema_version: str = FATIGUE_SIGMA_EXPERIMENT_MANIFEST_SCHEMA_VERSION
    formal_spec_adoption: bool = False
    base_profile_version: str = BASE_PROFILE_VERSION
    experiment_profile_version: str = FATIGUE_SIGMA_EXPERIMENT_PROFILE_VERSION
    reference_coefficients_modified: bool = True
    fatigue_policy_version: str = UNSELECTED_FULL_RECOVERY_POLICY_VERSION
    selected_fatigue_policy_version: str = SELECTED_SESSION_FATIGUE_POLICY_VERSION
    sigma_scaling_policy_version: str = SCALED_REFERENCE_SIGMA_POLICY_VERSION
    modified_fields: tuple[str, ...] = MODIFIED_FIELDS
    unchanged_reference_fields: tuple[str, ...] = UNCHANGED_REFERENCE_FIELDS

    def __post_init__(self) -> None:
        expected = {
            "lab_model_version": FATIGUE_EXPLORATION_CONVERGENCE_LAB_VERSION,
            "schema_version": FATIGUE_SIGMA_EXPERIMENT_MANIFEST_SCHEMA_VERSION,
            "formal_spec_adoption": False,
            "base_profile_version": BASE_PROFILE_VERSION,
            "experiment_profile_version": FATIGUE_SIGMA_EXPERIMENT_PROFILE_VERSION,
            "reference_coefficients_modified": True,
            "fatigue_policy_version": UNSELECTED_FULL_RECOVERY_POLICY_VERSION,
            "selected_fatigue_policy_version": SELECTED_SESSION_FATIGUE_POLICY_VERSION,
            "sigma_scaling_policy_version": SCALED_REFERENCE_SIGMA_POLICY_VERSION,
            "modified_fields": MODIFIED_FIELDS,
            "unchanged_reference_fields": UNCHANGED_REFERENCE_FIELDS,
        }
        if any(getattr(self, name) != value for name, value in expected.items()):
            raise ValueError("Stage 8A.1 experiment manifest values are fixed")

    def to_dict(self) -> dict[str, Any]:
        payload = {
            "lab_model_version": self.lab_model_version,
            "schema_version": self.schema_version,
            "formal_spec_adoption": self.formal_spec_adoption,
            "base_profile_version": self.base_profile_version,
            "experiment_profile_version": self.experiment_profile_version,
            "reference_coefficients_modified": self.reference_coefficients_modified,
            "fatigue_policy_version": self.fatigue_policy_version,
            "selected_fatigue_policy_version": self.selected_fatigue_policy_version,
            "sigma_scaling_policy_version": self.sigma_scaling_policy_version,
            "modified_fields": list(self.modified_fields),
            "unchanged_reference_fields": list(self.unchanged_reference_fields),
            "stationary_landscape_version": (
                "stationary_preference_landscape_v0_2"
            ),
            "stationary_user_profile_version": "stationary_user_type_profile_v2",
            "structured_convergence_version": (
                STRUCTURED_CONVERGENCE_DIAGNOSTICS_VERSION
            ),
            "paired_replicate_seed_policy_version": (
                PAIRED_REPLICATE_SEED_POLICY_VERSION
            ),
            "experiment_condition_schema_version": (
                FATIGUE_SIGMA_CONDITION_SCHEMA_VERSION
            ),
            "replicate_result_schema_version": (
                FATIGUE_SIGMA_REPLICATE_RESULT_SCHEMA_VERSION
            ),
            "session_outcome_schema_version": (
                FATIGUE_SIGMA_SESSION_OUTCOME_SCHEMA_VERSION
            ),
            "condition_summary_schema_version": (
                FATIGUE_SIGMA_CONDITION_SUMMARY_SCHEMA_VERSION
            ),
            "grid_summary_schema_version": FATIGUE_SIGMA_GRID_SUMMARY_SCHEMA_VERSION,
            "p_explore_modified": False,
            "epsilon_accept_modified": False,
            "q_coefficients_modified": False,
            "P_mapping_modified": False,
            "V_mapping_modified": False,
            "tau_mapping_modified": False,
            "stationary_preference": True,
            "moving_preference": False,
            "unselected_full_recovery": True,
            "convergence_is_diagnostic_only": True,
            "exploration_continues_after_convergence": True,
            "v2_reference_arm_available": True,
            "Monte_Carlo": False,
        }
        # The audit digest covers the manifest body.  It is then attached to
        # the exported object, avoiding an impossible self-referential hash.
        payload["experiment_manifest_digest"] = canonical_digest(payload)
        return payload


__all__ = ["FatigueSigmaExperimentManifest"]
