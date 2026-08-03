"""Stage 5C three-life state handoff and observation-only CSV contracts."""

from __future__ import annotations

import csv
import json
from dataclasses import replace
from pathlib import Path

import pytest

from symbiotic_sim_v2.digital_life.relation_memory.diagnostics import (
    ADAPTIVE_SIGNALS_CSV_FIELDS,
    ADAPTIVE_SIGNALS_CSV_FILENAME,
    INTRINSIC_PROFILES_CSV_FIELDS,
    INTRINSIC_PROFILES_CSV_FILENAME,
    PERSISTENT_STATES_CSV_FIELDS,
    PERSISTENT_STATES_CSV_FILENAME,
    RELATION_TRANSITIONS_CSV_FIELDS,
    RELATION_TRANSITIONS_CSV_FILENAME,
    SESSION_SUMMARY_CSV_FIELDS,
    SESSION_SUMMARY_CSV_FILENAME,
    adaptive_signal_digest,
    export_relation_memory_diagnostics,
    final_persistent_state_digest,
    intrinsic_profile_digest,
    relation_memory_transition_digest,
    session_summary_digest,
)
from symbiotic_sim_v2.digital_life.relation_memory.persistent_state import (
    RelationMemoryPersistentState,
)
from symbiotic_sim_v2.digital_life.relation_memory.state_io import (
    export_relation_memory_state_file,
    load_relation_memory_state_file,
    relation_memory_state_map_from_dict,
    relation_memory_state_map_from_json,
    relation_memory_state_map_to_dict,
    relation_memory_state_map_to_json,
)
from symbiotic_sim_v2.runtime.adaptive_closed_loop import (
    adaptive_digital_life_components,
    create_adaptive_relation_memory_closed_loop_simulation,
)

LIFE_IDS = ("life-red", "life-green", "life-blue")


def fresh_states() -> dict[str, RelationMemoryPersistentState]:
    return {
        life_id: RelationMemoryPersistentState.fresh(life_id)
        for life_id in LIFE_IDS
    }


def diagnostic_digests(components) -> tuple[str, ...]:
    return (
        intrinsic_profile_digest(components),
        adaptive_signal_digest(components),
        relation_memory_transition_digest(components),
        final_persistent_state_digest(components),
        session_summary_digest(components),
    )


def test_three_life_state_json_and_file_round_trip_are_canonical_and_read_only(
    tmp_path: Path,
) -> None:
    states = fresh_states()
    states["life-green"] = replace(
        states["life-green"],
        k_anchor=(0.2, 0.3, 0.4, 0.6),
        q=0.7,
        e=0.15,
        trial_count=3,
        session_count=8,
    )
    encoded = relation_memory_state_map_to_json(
        states,
        expected_digital_life_ids=LIFE_IDS,
    )
    assert encoded == json.dumps(
        relation_memory_state_map_to_dict(
            states,
            expected_digital_life_ids=LIFE_IDS,
        ),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    decoded = relation_memory_state_map_from_json(
        encoded,
        expected_digital_life_ids=LIFE_IDS,
    )
    assert dict(decoded) == states
    with pytest.raises(TypeError):
        decoded["life-green"] = states["life-green"]  # type: ignore[index]

    path = tmp_path / "nested" / "relation-state.json"
    assert export_relation_memory_state_file(
        path,
        states,
        expected_digital_life_ids=LIFE_IDS,
    ) == path
    assert path.read_text(encoding="utf-8") == encoded + "\n"
    assert dict(
        load_relation_memory_state_file(
            path,
            expected_digital_life_ids=LIFE_IDS,
        )
    ) == states


@pytest.mark.parametrize(
    "invalid",
    (
        {"life-red": RelationMemoryPersistentState.fresh("life-red").to_dict()},
        {
            **{
                life_id: RelationMemoryPersistentState.fresh(life_id).to_dict()
                for life_id in LIFE_IDS
            },
            "life-extra": RelationMemoryPersistentState.fresh("life-extra").to_dict(),
        },
        {
            "life-red": RelationMemoryPersistentState.fresh("life-green").to_dict(),
            "life-green": RelationMemoryPersistentState.fresh("life-red").to_dict(),
            "life-blue": RelationMemoryPersistentState.fresh("life-blue").to_dict(),
        },
    ),
    ids=("missing-roster", "unknown-roster", "state-id-mismatch"),
)
def test_state_import_rejects_non_exact_roster_or_identity(invalid) -> None:
    with pytest.raises(ValueError):
        relation_memory_state_map_from_dict(
            invalid,
            expected_digital_life_ids=LIFE_IDS,
        )


def test_state_json_rejects_duplicate_roster_keys() -> None:
    state = RelationMemoryPersistentState.fresh("life-red").to_json()
    encoded = f'{{"life-red":{state},"life-red":{state}}}'
    with pytest.raises(ValueError, match="duplicate"):
        relation_memory_state_map_from_json(
            encoded,
            expected_digital_life_ids=LIFE_IDS,
        )


def test_state_round_trip_preserves_full_execution_and_exports_final_state(
    tmp_path: Path,
) -> None:
    direct_states = fresh_states()
    direct_states["life-green"] = replace(
        direct_states["life-green"], session_count=10
    )
    initial_path = tmp_path / "initial.json"
    export_relation_memory_state_file(
        initial_path,
        direct_states,
        expected_digital_life_ids=LIFE_IDS,
    )
    loaded_states = load_relation_memory_state_file(
        initial_path,
        expected_digital_life_ids=LIFE_IDS,
    )

    direct = create_adaptive_relation_memory_closed_loop_simulation(
        initial_persistent_states_by_life_id=direct_states
    )
    reloaded = create_adaptive_relation_memory_closed_loop_simulation(
        initial_persistent_states_by_life_id=loaded_states
    )
    direct.engine.run_until_end()
    reloaded.engine.run_until_end()
    direct_components = adaptive_digital_life_components(direct)
    reloaded_components = adaptive_digital_life_components(reloaded)

    assert direct.engine.deterministic_digest() == reloaded.engine.deterministic_digest()
    assert diagnostic_digests(direct_components) == diagnostic_digests(
        reloaded_components
    )
    direct_final = {
        life_id: component.final_persistent_state()
        for life_id, component in direct_components.items()
    }
    reloaded_final = {
        life_id: component.final_persistent_state()
        for life_id, component in reloaded_components.items()
    }
    assert direct_final == reloaded_final
    assert all(state is not None for state in reloaded_final.values())

    final_path = tmp_path / "final.json"
    export_relation_memory_state_file(
        final_path,
        reloaded_final,  # type: ignore[arg-type]
        expected_digital_life_ids=LIFE_IDS,
    )
    assert dict(
        load_relation_memory_state_file(
            final_path,
            expected_digital_life_ids=LIFE_IDS,
        )
    ) == reloaded_final


def test_failed_execution_never_exposes_or_exports_a_committed_final_state(
    tmp_path: Path,
) -> None:
    simulation = create_adaptive_relation_memory_closed_loop_simulation()
    simulation.engine.start()
    simulation.engine.advance_by_us(239_000_000)
    with pytest.raises(RuntimeError, match="safety event limit"):
        simulation.engine.run_until_end(safety_event_limit=1)

    components = adaptive_digital_life_components(simulation)
    assert all(component.final_persistent_state() is None for component in components.values())
    assert all(
        not component.relation_memory_session_state().session_finalized
        for component in components.values()
    )
    with pytest.raises(RuntimeError, match="normal session closing"):
        final_persistent_state_digest(components)
    with pytest.raises(RuntimeError, match="normally finalized"):
        session_summary_digest(components)
    with pytest.raises(TypeError, match="persistent-state"):
        export_relation_memory_state_file(
            tmp_path / "must-not-exist.json",
            {
                life_id: component.final_persistent_state()
                for life_id, component in components.items()
            },  # type: ignore[arg-type]
            expected_digital_life_ids=LIFE_IDS,
        )
    assert not (tmp_path / "must-not-exist.json").exists()


def test_csv_export_has_exact_schemas_counts_and_no_digest_side_effect(
    tmp_path: Path,
) -> None:
    simulation = create_adaptive_relation_memory_closed_loop_simulation()
    simulation.engine.run_until_end()
    components = adaptive_digital_life_components(simulation)
    before = (simulation.engine.deterministic_digest(), *diagnostic_digests(components))

    paths = export_relation_memory_diagnostics(tmp_path, components)
    expected = {
        INTRINSIC_PROFILES_CSV_FILENAME: (INTRINSIC_PROFILES_CSV_FIELDS, 3),
        RELATION_TRANSITIONS_CSV_FILENAME: (RELATION_TRANSITIONS_CSV_FIELDS, 12),
        ADAPTIVE_SIGNALS_CSV_FILENAME: (ADAPTIVE_SIGNALS_CSV_FIELDS, 723),
        PERSISTENT_STATES_CSV_FILENAME: (PERSISTENT_STATES_CSV_FIELDS, 6),
        SESSION_SUMMARY_CSV_FILENAME: (SESSION_SUMMARY_CSV_FIELDS, 3),
    }
    assert {path.name for path in paths} == set(expected)
    for path in paths:
        with path.open(encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            rows = list(reader)
        fields, count = expected[path.name]
        assert tuple(reader.fieldnames or ()) == fields
        assert len(rows) == count

    after = (simulation.engine.deterministic_digest(), *diagnostic_digests(components))
    assert after == before

    swapped = dict(components)
    swapped["life-red"], swapped["life-green"] = (
        swapped["life-green"],
        swapped["life-red"],
    )
    with pytest.raises(ValueError, match="mapping keys"):
        intrinsic_profile_digest(swapped)
