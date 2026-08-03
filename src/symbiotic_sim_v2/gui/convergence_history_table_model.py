"""Read-only Stage 8A rolling-convergence history table."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from symbiotic_sim_v2.gui.session_history_table_model import (
    ImmutableProjectionTableModel,
    convergence_record_index,
    first_record_value,
    record_value,
    truth_value,
)


class ConvergenceHistoryTableModel(ImmutableProjectionTableModel):
    """Display evaluator outputs without running clustering in Qt."""

    FIELDS = (
        "evaluated_at_session",
        "window_sessions",
        "support",
        "holder",
        "member_indices",
        "outlier_indices",
        "medoid_hue_bpm",
        "maximum_distance",
        "state",
        "response_gap",
        "nearest_peak",
    )
    HEADERS = (
        "evaluated at session",
        "window session indices",
        "support",
        "holder",
        "member indices",
        "outlier indices",
        "medoid Hue / BPM",
        "max pairwise distance",
        "state",
        "response gap",
        "nearest peak / sigma distance",
    )

    def set_records(
        self,
        convergence_records: Sequence[Any],
        truth_alignment_records: Sequence[Any] = (),
    ) -> None:
        truth_by_session = {
            index: truth
            for truth in truth_alignment_records
            if (index := convergence_record_index(truth)) is not None
        }
        rows = []
        for record in convergence_records:
            evaluated_at = convergence_record_index(record)
            truth = truth_by_session.get(evaluated_at, record)
            hue = first_record_value(
                record,
                ("medoid_hue_degree", "medoid_hue"),
            )
            bpm = first_record_value(
                record,
                ("medoid_blink_bpm", "medoid_bpm"),
            )
            rows.append(
                {
                    "evaluated_at_session": evaluated_at,
                    "window_sessions": first_record_value(
                        record,
                        ("window_session_indices", "valid_window_session_indices"),
                        (),
                    ),
                    "support": record_value(record, "support_count", 0),
                    "holder": first_record_value(
                        record,
                        ("holder_id", "dominant_holder_id"),
                    ),
                    "member_indices": record_value(
                        record,
                        "member_session_indices",
                        (),
                    ),
                    "outlier_indices": record_value(
                        record,
                        "outlier_session_indices",
                        (),
                    ),
                    "medoid_hue_bpm": (
                        None if hue is None or bpm is None else (hue, bpm)
                    ),
                    "maximum_distance": first_record_value(
                        record,
                        ("maximum_pairwise_distance", "max_pairwise_distance"),
                    ),
                    "state": first_record_value(
                        record,
                        ("convergence_state", "state"),
                    ),
                    "response_gap": truth_value(truth, "response_gap"),
                    "nearest_peak": _nearest_peak(truth),
                }
            )
        self.set_projected_rows(rows)


def _nearest_peak(record: Any) -> str | None:
    peak_id = truth_value(record, "nearest_peak_id")
    distance = truth_value(record, "distance_to_nearest_peak_center")
    if peak_id is None or distance is None:
        return None
    return f"{peak_id} / {float(distance):.6f} σ"


__all__ = ["ConvergenceHistoryTableModel"]
