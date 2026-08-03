"""Stage 7.1 diagnostic-only change and Stage 1-7 regression boundaries."""

from __future__ import annotations

import pytest

from symbiotic_sim_v2.runtime.closed_loop import (
    LightResponsiveClosedLoopSimulation,
    create_light_responsive_closed_loop_simulation,
)
from symbiotic_sim_v2.runtime.light_simulation import (
    LightFeedbackSimulation,
    create_light_feedback_simulation,
)


@pytest.fixture(scope="module")
def stage71_standard() -> LightResponsiveClosedLoopSimulation:
    simulation = create_light_responsive_closed_loop_simulation()
    simulation.engine.run_until_end()
    return simulation


@pytest.fixture(scope="module")
def unchanged_stage6() -> LightFeedbackSimulation:
    simulation = create_light_feedback_simulation()
    simulation.engine.run_until_end()
    return simulation


def test_stage7_formal_physiology_heartbeat_and_samples_are_byte_stable(
    stage71_standard: LightResponsiveClosedLoopSimulation,
) -> None:
    simulation = stage71_standard
    component = simulation.component
    assert simulation.engine.deterministic_digest() == (
        "db9948271c0a664cd990c9954b131ebefc855a553005225241a6f94ac00625bf"
    )
    assert len(simulation.engine.executed_events()) == 3_281
    assert component.heartbeat_digest() == (
        "3392698943c200a9ab08964644ca72d56f50dfc1944c225b8c3e7933c5a229ae"
    )
    assert component.responsive_diagnostic_digest() == (
        "f8240cabbc882ceef81b537c29f907b60c23bad3bc207dac3c4a51b52aaca3cd"
    )
    assert component.response_sample_digest() == (
        "b230c3d38ca3d1f85ba910c5970f667970c8d6e66533c84b3ecca7abe7c30bb7"
    )
    assert len(component.heartbeat_records()) == 277
    assert len(component.response_samples()) == 2_401
    assert [
        component.response_at(time_us)
        for time_us in (90_000_000, 120_000_000, 180_000_000, 239_999_999)
    ] == pytest.approx(
        (
            0.974803684362126,
            0.9994074394523207,
            0.9999996722640228,
            0.9999999998187343,
        )
    )


def test_stage7_h10_garden_life_and_light_results_are_unchanged(
    stage71_standard: LightResponsiveClosedLoopSimulation,
) -> None:
    simulation = stage71_standard
    assert simulation.polar_h10_component.measurement_digest() == (
        "e993c8bf0c6e3a668e0656a9f1b0bd9be0225b60999f4cbdb630446f5be410a1"
    )
    assert simulation.garden_input_component.evaluation_digest() == (
        "26ff497e385e345d5e69051db757121ffa2afea1f7c68d3844b2c7df4a9de68e"
    )
    assert simulation.garden_input_component.signal_digest() == (
        "14c73cc1c7349f169d1864475daef2621356e2f804ff1796e89701dca86699d8"
    )
    assert simulation.garden_output_component.touch_digest() == (
        "1fb2e4c07fddd1cc2d133b5fdc9728a4b2b570592d72b1177e523088f9ad4268"
    )
    assert simulation.garden_output_component.qualified_b_digest() == (
        "2f605a3514387bb58de0e3c1fd0b18f4605068e1853e749e63180ab542cc46fb"
    )
    assert simulation.garden_output_component.feedback_digest() == (
        "121c9bfdee73a3411864829f146958afc134fc2b08d96c70a71f20d11fc0ff62"
    )
    assert simulation.mapper.command_digest() == (
        "a908bd293d5cb4fdf57ce522ee96bd40d8751f2480654ef63902c16136096542"
    )
    assert simulation.device.stimulus_state_digest() == (
        "a699a59a01b81e9b81a57d182a9f8cbcf5b0483abe5cff83180ea86d44070dea"
    )
    assert {
        life_id: (component.first_round_digest(), component.second_round_digest())
        for life_id, component in simulation.digital_life_components.items()
    } == {
        "life-blue": (
            "b2181611e4f9fd48184ac7b642d2f88d06f9119cd6fa5d874bb1259704ce5977",
            "c0ead66031483ca20b7b80bf69df2921617cb66335408980661b8237df86c29c",
        ),
        "life-green": (
            "c94de8fd4bb7ebad793b5708b70580a3825bca1c547cb9301a9e120ca0e20673",
            "fc520f76e123eefc20293a3eb4d97c297bd5055cbe23d1c42d409ff53395bab5",
        ),
        "life-red": (
            "a7184c20698d00c244d3e77637fd6fe8d8226170a6bdd19d3c1b273a093efbf5",
            "c0ead66031483ca20b7b80bf69df2921617cb66335408980661b8237df86c29c",
        ),
    }


def test_standard_run_exposes_separate_audit_and_epoch_histories(
    stage71_standard: LightResponsiveClosedLoopSimulation,
) -> None:
    component = stage71_standard.component
    audits = component.physical_audit_segments()
    epochs = component.response_dynamics_epoch_records()
    assert len(component.light_receipt_records()) == 241
    assert len(audits) == len(epochs) == 2
    assert tuple(segment.response_dynamics_epoch_index for segment in audits) == (0, 1)
    assert tuple(epoch.epoch_index for epoch in epochs) == (0, 1)
    assert audits[0].end_time_us == epochs[0].end_time_us == 60_551_540
    assert audits[-1].end_time_us == epochs[-1].end_time_us == 240_000_000
    assert component.snapshot().physical_stimulus_change_count == 2
    assert component.snapshot().response_target_change_count == 2
    closing_receipt = component.light_receipt_records()[-1]
    assert closing_receipt.event_time_us == 240_000_000
    assert closing_receipt.audit_segment_index is None
    assert closing_receipt.response_dynamics_epoch_index is None
    assert all(
        receipt.audit_segment_index is not None
        and 0 <= receipt.audit_segment_index < len(audits)
        and receipt.response_dynamics_epoch_index is not None
        and 0 <= receipt.response_dynamics_epoch_index < len(epochs)
        for receipt in component.light_receipt_records()[:-1]
    )


def test_stage1_through_stage6_closed_loop_boundary_remains_exact(
    unchanged_stage6: LightFeedbackSimulation,
) -> None:
    simulation = unchanged_stage6
    upstream = simulation.upstream_simulation
    assert simulation.engine.deterministic_digest() == (
        "f2ef166cd2bbea252d2c848b7f67d80cad1840534fe736d792087639b5b2a833"
    )
    assert len(simulation.engine.executed_events()) == 3_287
    assert upstream.virtual_user_component.heartbeat_digest() == (
        "dfc32d05a372482a81a40ffbb9dc721aed8edcada4709a4dcb86e76719ddf17b"
    )
    assert upstream.polar_h10_component.measurement_digest() == (
        "cff3715c4ddf73b3b8838bf3725f0ef68fc6452110ae89bdf0c6aab3a3bf585b"
    )
    assert upstream.garden_input_component.evaluation_digest() == (
        "371f7d7618b8dbc1259f17765409fed1167eaa8fd4bdf62bef743891b726dd1e"
    )
    assert upstream.garden_input_component.signal_digest() == (
        "0f68cde436e712e7dad5608ad6347af216cee80945ca951404cf511825785add"
    )
    assert upstream.garden_output_component.touch_digest() == (
        "0d5f8671fd3859f74be7c758954952c8976eb02dcea62b7074ec459063a76c75"
    )
    assert upstream.garden_output_component.qualified_b_digest() == (
        "6157d8251af0e0ceb784b664d90d01368b8506efeb37665962244f991b6a57b7"
    )
    assert simulation.mapper.command_digest() == (
        "306648650d4b286a48b3f9188f7fd640764b05fb135c581c4b9d00b487d06020"
    )
    assert simulation.device.stimulus_state_digest() == (
        "1dbf214e1448802a665031f73fb798cdbf04471210aeddf438c68b72b616265e"
    )
    assert simulation.device.segment_digest() == (
        "9dabc1b018b52f9be603ba164655f3c5fa79ff4f6579ae8a6bfd48047d8fd763"
    )
    assert simulation.device.waveform_sample_digest() == (
        "a075f488a588d7d2f78548e4ae339e7cac59c88f8e4508b2a89f0ca6e36cc0c0"
    )
