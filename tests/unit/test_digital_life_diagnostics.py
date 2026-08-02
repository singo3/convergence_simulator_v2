"""Stage 5A CSV export field, value, and observation-only tests."""

from __future__ import annotations

import csv

from symbiotic_sim_v2.digital_life.diagnostics import (
    EVALUATION_UPDATE_CSV_FIELDS,
    EVALUATION_UPDATE_CSV_FILENAME,
    FIRST_ROUND_CSV_FIELDS,
    FIRST_ROUND_CSV_FILENAME,
    export_evaluation_updates_csv,
    export_first_round_diagnostics_csv,
)
from symbiotic_sim_v2.digital_life.records import (
    DigitalLifeEvaluationUpdateRecord,
    DigitalLifeFirstRoundRecord,
)


def first_round_record() -> DigitalLifeFirstRoundRecord:
    return DigitalLifeFirstRoundRecord(
        signal_index=60,
        signal_time_us=60_000_000,
        digital_life_id="life-green",
        role="green",
        phase="bundle_0",
        bundle_index=0,
        window_role="evaluation",
        session_status="active",
        s=1,
        n_current=0.2,
        n_available=True,
        n_baseline_session=0.1,
        baseline_available=True,
        valid_evaluation_revision=2,
        is_new_valid_evaluation=True,
        source_evaluation_id="session-001-bundle-0",
        source_evaluation_kind="bundle",
        source_evaluation_quality="valid",
        nd=1.0,
        w=1.0,
        p=0.4,
        p_intrinsic=0.4,
        e=0.0,
        q=0.5,
        v=0.35,
        k_anchor=(0.5, 0.5, 0.5, 0.5),
        k_current=(0.1, 0.2, 0.3, 0.4),
        b_f=0.336,
        b_a=0.5,
        b_t=0.3,
        b_d=0.5,
        tau=0.533,
        birth_phase=0.0000001,
        touch_enabled=True,
        touch_dispatched=False,
        second_round_connected=False,
        g_status="not_connected",
    )


def evaluation_record() -> DigitalLifeEvaluationUpdateRecord:
    return DigitalLifeEvaluationUpdateRecord(
        evaluation_id="session-001-bundle-0",
        evaluation_kind="bundle",
        bundle_index=0,
        event_time_us=120_000_000,
        quality="valid",
        is_valid=True,
        n_revision=2,
        n=0.2,
        n_baseline_session=0.1,
        previous_nd=0.5,
        new_nd=1.0,
        previous_w=0.5,
        new_w=1.0,
        applied=True,
        skip_reason=None,
    )


def read_csv(path) -> tuple[tuple[str, ...], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as csv_file:
        reader = csv.DictReader(csv_file)
        rows = list(reader)
        return tuple(reader.fieldnames or ()), rows


def test_first_round_export_has_exact_columns_and_does_not_mutate_records(tmp_path) -> None:
    records = (first_round_record(),)
    before = records[0].to_dict()

    path = export_first_round_diagnostics_csv(tmp_path, records)
    fields, rows = read_csv(path)

    assert path == tmp_path / FIRST_ROUND_CSV_FILENAME
    assert fields == FIRST_ROUND_CSV_FIELDS
    assert len(rows) == 1
    assert rows[0]["signal_time_seconds"] == "60.0"
    assert [rows[0][name] for name in ("k_F", "k_A", "k_T", "k_D")] == [
        "0.1",
        "0.2",
        "0.3",
        "0.4",
    ]
    assert rows[0]["S"] == "1"
    assert rows[0]["N_current"] == "0.2"
    assert rows[0]["touch_dispatched"] == "False"
    assert records[0].to_dict() == before


def test_evaluation_export_has_exact_columns_and_preserves_null(tmp_path) -> None:
    records = (evaluation_record(),)
    before = records[0].to_dict()

    path = export_evaluation_updates_csv(tmp_path, records)
    fields, rows = read_csv(path)

    assert path == tmp_path / EVALUATION_UPDATE_CSV_FILENAME
    assert fields == EVALUATION_UPDATE_CSV_FIELDS
    assert len(rows) == 1
    assert rows[0]["N"] == "0.2"
    assert rows[0]["previous_Nd"] == "0.5"
    assert rows[0]["skip_reason"] == ""
    assert records[0].to_dict() == before
