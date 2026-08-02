"""End-to-end Stage 6 light scenario and upstream-regression checks."""

from __future__ import annotations

import csv
from pathlib import Path

import pytest

from symbiotic_sim_v2.devices.polar_h10.scenario import create_polar_h10_simulation
from symbiotic_sim_v2.devices.virtual_light.diagnostics import (
    export_light_diagnostics,
)
from symbiotic_sim_v2.digital_life.diagnostics import (
    EVALUATION_UPDATE_CSV_FILENAME,
    FIRST_ROUND_CSV_FILENAME,
    export_evaluation_updates_csv,
    export_first_round_diagnostics_csv,
)
from symbiotic_sim_v2.digital_life.scenario import (
    create_single_digital_life_simulation,
)
from symbiotic_sim_v2.digital_life.second_round_diagnostics import (
    SECOND_ROUND_CSV_FILENAME,
    export_second_round_diagnostics_csv,
)
from symbiotic_sim_v2.domain.event_types import (
    GARDEN_EVALUATION_FINALIZED_EVENT_TYPE,
    GARDEN_INPUT_SIGNAL_EVENT_TYPE,
    SIMULATION_COMPLETE_EVENT_TYPE,
)
from symbiotic_sim_v2.garden.input_layer.diagnostics import (
    export_garden_input_diagnostics,
)
from symbiotic_sim_v2.garden.input_layer.scenario import (
    create_garden_input_simulation,
)
from symbiotic_sim_v2.garden.light_mapper.events import LIGHT_COMMAND_EVENT_TYPE
from symbiotic_sim_v2.garden.output_layer.diagnostics import (
    export_garden_output_diagnostics,
)
from symbiotic_sim_v2.garden.output_layer.events import (
    DIGITAL_LIFE_TOUCH_EVENT_TYPE,
    GARDEN_HOLDER_RELEASE_EVENT_TYPE,
    GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE,
    GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_TYPE,
    GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_TYPE,
    GARDEN_QUALIFIED_B_EVENT_TYPE,
)
from symbiotic_sim_v2.runtime.light_simulation.scenario import (
    LightFeedbackSimulation,
    create_light_feedback_simulation,
)
from symbiotic_sim_v2.runtime.multi_life.scenario import (
    ThreeDigitalLifeCompetitionSimulation,
    create_three_digital_life_competition_simulation,
)
from symbiotic_sim_v2.simulation.demo_scenario import create_demo_engine
from symbiotic_sim_v2.virtual_user.scenario import create_virtual_user_simulation


@pytest.fixture(scope="module")
def light_simulation() -> LightFeedbackSimulation:
    simulation = create_light_feedback_simulation()
    simulation.engine.run_until_end()
    return simulation


@pytest.fixture(scope="module")
def stage5b_simulation() -> ThreeDigitalLifeCompetitionSimulation:
    simulation = create_three_digital_life_competition_simulation()
    simulation.engine.run_until_end()
    return simulation


def test_standard_light_scenario_counts_mapping_state_and_segments(
    light_simulation: LightFeedbackSimulation,
) -> None:
    simulation = light_simulation
    mapper = simulation.mapper
    device = simulation.device
    commands = device.command_records()
    states = device.stimulus_state_records()
    segments = device.stimulus_segments()
    active_commands = tuple(record for record in commands if record.active)
    inactive_commands = tuple(record for record in commands if not record.active)

    assert simulation.engine.clock.current_time_us == 240_000_000
    assert len(simulation.engine.executed_events()) == 3_287
    assert len(mapper.command_records()) == len(commands) == len(states) == 241
    assert len(active_commands) == 180
    assert len(inactive_commands) == 61
    assert len(segments) == 240
    assert sum(segment.active for segment in segments) == 180
    assert sum(not segment.active for segment in segments) == 60
    assert mapper.command_digest() == device.command_digest()

    first = active_commands[0]
    assert first.source_signal_index == 60
    assert first.effective_time_us == 60_551_540
    assert first.qualification_holder_id == "life-green"
    assert first.source_b == (125 / 360, 0.5, 0.5, 0.5)
    assert first.hue_degree == first.render_hue_degree == 125.0
    assert first.blink_bpm == 87.5
    assert first.saturation == 1.0
    assert (first.value_min, first.value_center, first.value_max) == (
        0.35,
        0.425,
        0.5,
    )
    assert first.value_amplitude == 0.075
    assert first.waveform == "sine"
    first_state = states[first.command_index]
    assert first_state.phase_cycles_at_start == 0.0
    assert first_state.value_at_start == 0.425
    assert first_state.phase_reset

    assert active_commands[-1].effective_time_us == 239_589_850
    closing = commands[-1]
    assert closing.source_signal_index == 240
    assert closing.effective_time_us == 240_000_000
    assert not closing.active
    assert closing.qualification_holder_id is closing.source_b is None
    final = device.snapshot()
    assert final.completed and not final.active
    assert final.current_value == 0.0
    assert final.phase_cycles is None
    assert final.phase_reset_count == 1
    assert final.phase_continuation_count == 179

    assert segments[0].start_time_us == 0
    assert segments[-1].end_time_us == 240_000_000
    assert all(segment.duration_us > 0 for segment in segments)
    assert all(
        left.end_time_us == right.start_time_us
        for left, right in zip(segments, segments[1:], strict=False)
    )
    assert all(
        left.phase_cycles_at_end == right.phase_cycles_at_start
        for left, right in zip(segments, segments[1:], strict=False)
        if left.active and right.active
    )
    assert all(
        segment.phase_cycles_at_start is segment.phase_cycles_at_end is None
        for segment in segments
        if not segment.active
    )


def test_stage6_event_ordering_preserves_round_and_closing_boundaries(
    light_simulation: LightFeedbackSimulation,
) -> None:
    events = light_simulation.engine.executed_events()

    first_active_types = {
        DIGITAL_LIFE_TOUCH_EVENT_TYPE,
        GARDEN_QUALIFIED_B_EVENT_TYPE,
        LIGHT_COMMAND_EVENT_TYPE,
        "light_stimulus_state",
    }
    first_active_boundary = tuple(
        event
        for event in events
        if event.scheduled_time_us == 60_551_540
        and event.event_type in first_active_types
    )
    assert [event.event_type for event in first_active_boundary] == [
        DIGITAL_LIFE_TOUCH_EVENT_TYPE,
        GARDEN_QUALIFIED_B_EVENT_TYPE,
        LIGHT_COMMAND_EVENT_TYPE,
        "light_stimulus_state",
    ]
    assert [event.priority for event in first_active_boundary] == [60, 65, 66, 67]

    first_finalize = tuple(
        event
        for event in events
        if event.scheduled_time_us == 60_999_999
        and event.event_type
        in {
            GARDEN_OUTPUT_ROUND_FINALIZE_EVENT_TYPE,
            GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE,
        }
    )
    assert [event.priority for event in first_finalize] == [70, 80, 80, 80]

    inactive_types = {
        GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_TYPE,
        GARDEN_QUALIFIED_B_EVENT_TYPE,
        LIGHT_COMMAND_EVENT_TYPE,
        "light_stimulus_state",
        GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE,
    }
    baseline_boundary = tuple(
        event
        for event in events
        if event.scheduled_time_us == 1_000_000
        and event.event_type in inactive_types
    )
    assert [event.priority for event in baseline_boundary] == [
        31,
        65,
        66,
        67,
        80,
        80,
        80,
    ]

    closing_types = {
        GARDEN_EVALUATION_FINALIZED_EVENT_TYPE,
        GARDEN_INPUT_SIGNAL_EVENT_TYPE,
        GARDEN_OUTPUT_NO_TOUCH_FINALIZE_EVENT_TYPE,
        GARDEN_QUALIFIED_B_EVENT_TYPE,
        LIGHT_COMMAND_EVENT_TYPE,
        "light_stimulus_state",
        GARDEN_INTEROCEPTIVE_FEEDBACK_EVENT_TYPE,
        GARDEN_HOLDER_RELEASE_EVENT_TYPE,
        SIMULATION_COMPLETE_EVENT_TYPE,
    }
    closing = tuple(
        event
        for event in events
        if event.scheduled_time_us == 240_000_000
        and event.event_type in closing_types
    )
    assert [event.priority for event in closing] == [
        25,
        30,
        31,
        65,
        66,
        67,
        80,
        80,
        80,
        90,
        100,
    ]


def test_stage1_through_stage5b1_exact_digests_remain_unchanged() -> None:
    stage1 = create_demo_engine()
    stage1.run_until_end()
    assert stage1.deterministic_digest() == (
        "1c4217065fa29316e7ead83c4d604e87f9fe8fe46e82b689b5566dbc9890598d"
    )

    stage2 = create_virtual_user_simulation()
    stage2.engine.run_until_end()
    assert stage2.component.heartbeat_digest() == (
        "4c039f5f1b5cc3cd78682cca890a8a6ec70510a52b4ad4addeabcb0ecd3ae765"
    )
    assert stage2.component.diagnostic_digest() == (
        "ef0bc8c644e8b5f6fc2c3b58ef825491e49e005bc0c6c22a9f0c62c66168cd8f"
    )
    assert stage2.engine.deterministic_digest() == (
        "761a2dc6b2b03c4d538a85d95160f2ecc731e301a1362006ee97ea575872bddb"
    )

    stage3 = create_polar_h10_simulation()
    stage3.engine.run_until_end()
    assert stage3.polar_h10_component.measurement_digest() == (
        "69d645f9e742f8cb9dbb16d9deb65ff10ce77b31c66c35e8fd01cfc5c97272b3"
    )
    assert stage3.engine.deterministic_digest() == (
        "d5a174f007a160a1442569b017fe404806db61cc18e0b6a0cda99cd2995b6572"
    )

    stage4 = create_garden_input_simulation()
    stage4.engine.run_until_end()
    garden = stage4.garden_input_component
    assert garden.artifact_digest() == (
        "4bea74309fcc62922325bd94a6a6a8561daf63740a4fe1b853c9a26f3b6838f1"
    )
    assert garden.evaluation_digest() == (
        "371f7d7618b8dbc1259f17765409fed1167eaa8fd4bdf62bef743891b726dd1e"
    )
    assert garden.signal_digest() == (
        "0f68cde436e712e7dad5608ad6347af216cee80945ca951404cf511825785add"
    )
    assert stage4.engine.deterministic_digest() == (
        "34b18fa72f51cd5cccf9ef7107000d0ef2fdeeb4f62c3e8d7f0ae3de1cd19b72"
    )

    stage5a = create_single_digital_life_simulation()
    stage5a.engine.run_until_end()
    life = stage5a.digital_life_component
    assert life.first_round_digest() == (
        "661c2c74942d6b217a635fb4f2cb142bee8cff2e0e842cd21ccdd511682028b8"
    )
    assert life.evaluation_update_digest() == (
        "f7bf973cc20a2af77ccd7b38fa0e2407801353890a23cc1b3e30e9d7feeba4c3"
    )
    assert stage5a.engine.deterministic_digest() == (
        "34b18fa72f51cd5cccf9ef7107000d0ef2fdeeb4f62c3e8d7f0ae3de1cd19b72"
    )

    stage5b = create_three_digital_life_competition_simulation()
    stage5b.engine.run_until_end()
    output = stage5b.garden_output_component
    assert output.touch_digest() == (
        "0d5f8671fd3859f74be7c758954952c8976eb02dcea62b7074ec459063a76c75"
    )
    assert output.qualification_digest() == (
        "1dd880f811bf1dd6e56e2842a65d565aa82c7e4fb61cbb4a5b2f123946102eed"
    )
    assert output.qualified_b_digest() == (
        "6157d8251af0e0ceb784b664d90d01368b8506efeb37665962244f991b6a57b7"
    )
    assert output.feedback_digest() == (
        "121c9bfdee73a3411864829f146958afc134fc2b08d96c70a71f20d11fc0ff62"
    )
    assert stage5b.engine.deterministic_digest() == (
        "fa68733a98a962fcad7aeb58d7ec12439e860d8d02c43beaae42e345d5a0884f"
    )


def test_light_integration_does_not_change_upstream_holder_g_e_q_k_rri_or_n(
    light_simulation: LightFeedbackSimulation,
    stage5b_simulation: ThreeDigitalLifeCompetitionSimulation,
) -> None:
    integrated = light_simulation.upstream
    baseline = stage5b_simulation
    assert integrated.virtual_user_component.heartbeat_digest() == (
        baseline.virtual_user_component.heartbeat_digest()
    )
    assert integrated.polar_h10_component.measurement_digest() == (
        baseline.polar_h10_component.measurement_digest()
    )
    for digest_name in ("artifact_digest", "evaluation_digest", "signal_digest"):
        assert getattr(integrated.garden_input_component, digest_name)() == getattr(
            baseline.garden_input_component,
            digest_name,
        )()
    for digest_name in (
        "touch_digest",
        "qualification_digest",
        "qualified_b_digest",
        "feedback_digest",
    ):
        assert getattr(integrated.garden_output_component, digest_name)() == getattr(
            baseline.garden_output_component,
            digest_name,
        )()
    integrated_holder = (
        integrated.garden_output_component.snapshot().last_assigned_holder_id
    )
    baseline_holder = baseline.garden_output_component.snapshot().last_assigned_holder_id
    assert integrated_holder == baseline_holder == "life-green"
    assert integrated.garden_output_component.snapshot().qualification_holder_id is None
    for life_id in sorted(integrated.digital_life_components):
        actual = integrated.digital_life_components[life_id]
        expected = baseline.digital_life_components[life_id]
        assert actual.first_round_digest() == expected.first_round_digest()
        assert actual.second_round_digest() == expected.second_round_digest()
        actual_snapshot = actual.snapshot()
        expected_snapshot = expected.snapshot()
        assert (
            actual_snapshot.current_g,
            actual_snapshot.e,
            actual_snapshot.q,
            actual_snapshot.k_anchor,
            actual_snapshot.k_current,
            actual_snapshot.q_update_count,
            actual_snapshot.k_update_count,
        ) == (
            expected_snapshot.current_g,
            expected_snapshot.e,
            expected_snapshot.q,
            expected_snapshot.k_anchor,
            expected_snapshot.k_current,
            expected_snapshot.q_update_count,
            expected_snapshot.k_update_count,
        )


def _combined_second_round(simulation: ThreeDigitalLifeCompetitionSimulation):
    return tuple(
        sorted(
            (
                record
                for component in simulation.digital_life_components.values()
                for record in component.second_round_records()
            ),
            key=lambda record: (record.signal_index, record.digital_life_id),
        )
    )


def _csv_rows_without_input_event_id(path: Path) -> tuple[dict[str, str], ...]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = tuple(csv.DictReader(handle))
    return tuple(
        {key: value for key, value in row.items() if key != "input_event_id"}
        for row in rows
    )


def _assert_upstream_csv_directories_equal(expected: Path, actual: Path) -> None:
    expected_files = tuple(
        sorted(path.relative_to(expected) for path in expected.rglob("*.csv"))
    )
    actual_files = tuple(sorted(path.relative_to(actual) for path in actual.rglob("*.csv")))
    assert actual_files == expected_files
    for relative in expected_files:
        expected_path = expected / relative
        actual_path = actual / relative
        if "input_event_id" in expected_path.read_text(encoding="utf-8").splitlines()[0]:
            # Event IDs reflect the integrated scheduler's extra Stage 6 events.
            # All physiological and Garden diagnostic fields remain invariant.
            assert _csv_rows_without_input_event_id(actual_path) == (
                _csv_rows_without_input_event_id(expected_path)
            )
        else:
            assert actual_path.read_bytes() == expected_path.read_bytes()


def test_stage6_wrapper_preserves_stage5b1_upstream_csv_content(
    light_simulation: LightFeedbackSimulation,
    stage5b_simulation: ThreeDigitalLifeCompetitionSimulation,
    tmp_path: Path,
) -> None:
    integrated = light_simulation.upstream
    baseline_root = tmp_path / "baseline"
    integrated_root = tmp_path / "integrated"

    export_garden_input_diagnostics(
        baseline_root / "stage4",
        stage5b_simulation.garden_input_component,
    )
    export_garden_input_diagnostics(
        integrated_root / "stage4",
        integrated.garden_input_component,
    )

    baseline_green = stage5b_simulation.digital_life_components["life-green"]
    integrated_green = integrated.digital_life_components["life-green"]
    for root, component in (
        (baseline_root / "stage5a", baseline_green),
        (integrated_root / "stage5a", integrated_green),
    ):
        export_first_round_diagnostics_csv(
            root / FIRST_ROUND_CSV_FILENAME,
            component.first_round_records(),
        )
        export_evaluation_updates_csv(
            root / EVALUATION_UPDATE_CSV_FILENAME,
            component.evaluation_update_records(),
        )

    for root, simulation in (
        (baseline_root / "stage5b1", stage5b_simulation),
        (integrated_root / "stage5b1", integrated),
    ):
        export_garden_output_diagnostics(root, simulation.garden_output_component)
        export_second_round_diagnostics_csv(
            root / SECOND_ROUND_CSV_FILENAME,
            _combined_second_round(simulation),
        )

    _assert_upstream_csv_directories_equal(baseline_root, integrated_root)


def test_stage6_csv_export_has_exact_row_counts_and_does_not_change_digests(
    light_simulation: LightFeedbackSimulation,
    tmp_path: Path,
) -> None:
    simulation = light_simulation
    before = (
        simulation.mapper.command_digest(),
        simulation.device.stimulus_state_digest(),
        simulation.device.segment_digest(),
        simulation.device.waveform_sample_digest(),
        simulation.engine.deterministic_digest(),
    )
    paths = export_light_diagnostics(
        tmp_path,
        simulation.device,
        simulation.mapper.command_records(),
    )
    for path, expected_rows in (
        (paths.commands, 241),
        (paths.stimulus_states, 241),
        (paths.stimulus_segments, 240),
        (paths.waveform_samples, 12_001),
    ):
        with path.open(encoding="utf-8", newline="") as csv_file:
            assert sum(1 for _row in csv.DictReader(csv_file)) == expected_rows
    after = (
        simulation.mapper.command_digest(),
        simulation.device.stimulus_state_digest(),
        simulation.device.segment_digest(),
        simulation.device.waveform_sample_digest(),
        simulation.engine.deterministic_digest(),
    )
    assert after == before
