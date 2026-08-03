"""Read-only comparison rows for Stage 8A stationary user types."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from symbiotic_sim_v2.gui.session_history_table_model import (
    ImmutableProjectionTableModel,
    first_record_value,
    record_value,
    truth_value,
)


class UserTypeComparisonTableModel(ImmutableProjectionTableModel):
    """Project independent comparison results supplied by the diagnostic runner."""

    FIELDS = (
        "user_type",
        "first_convergence",
        "state",
        "dominant_life",
        "hue_bpm",
        "truth",
        "explore_count",
        "accepted_count",
        "outlier_rate",
    )
    HEADERS = (
        "user type",
        "first convergence",
        "state",
        "dominant life",
        "Hue / BPM",
        "correct / suboptimal / N/A",
        "explore count",
        "accepted count",
        "outlier rate",
    )

    def set_records(self, comparison_rows: Sequence[Any]) -> None:
        rows = []
        for record in comparison_rows:
            hue = first_record_value(
                record,
                ("dominant_hue_degree", "medoid_hue_degree", "medoid_hue"),
            )
            bpm = first_record_value(
                record,
                ("dominant_blink_bpm", "medoid_blink_bpm", "medoid_bpm"),
            )
            rows.append(
                {
                    "user_type": first_record_value(
                        record,
                        ("user_type_id", "stationary_user_type_id"),
                    ),
                    "first_convergence": record_value(
                        record,
                        "first_convergence_session_index",
                    ),
                    "state": first_record_value(
                        record,
                        ("current_convergence_state", "convergence_state", "state"),
                    ),
                    "dominant_life": first_record_value(
                        record,
                        ("dominant_holder_id", "holder_id"),
                    ),
                    "hue_bpm": None if hue is None or bpm is None else (hue, bpm),
                    "truth": truth_value(
                        record,
                        "truth_classification",
                        truth_value(record, "classification"),
                    ),
                    "explore_count": record_value(record, "explore_count", 0),
                    "accepted_count": first_record_value(
                        record,
                        ("accepted_candidate_count", "accepted_count"),
                        0,
                    ),
                    "outlier_rate": first_record_value(
                        record,
                        ("post_convergence_outlier_rate", "outlier_rate"),
                    ),
                }
            )
        self.set_projected_rows(rows)


__all__ = ["UserTypeComparisonTableModel"]
