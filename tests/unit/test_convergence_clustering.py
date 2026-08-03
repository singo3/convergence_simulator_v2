"""Rolling complete-link majority, tie-break, and state-transition tests."""

from __future__ import annotations

import dataclasses
import json
import math

import pytest

from symbiotic_sim_v2.convergence import (
    RollingConvergenceConfig,
    RollingConvergenceEvaluator,
    RollingConvergenceRecord,
    SessionPatternObservation,
    evaluate_convergence_history,
    select_dominant_cluster,
)


def observed(
    index: int,
    hue: float = 129.0,
    bpm: float = 125.0,
    holder: str = "life-green",
    *,
    exploration: str = "hold",
    accepted: bool = False,
) -> SessionPatternObservation:
    return SessionPatternObservation(
        session_index=index,
        valid_for_convergence=True,
        invalid_reason=None,
        holder_id=holder,
        hue_degree=hue,
        blink_bpm=bpm,
        exploration_decision=exploration,
        candidate_generated=exploration == "explore",
        candidate_accepted=accepted,
    )


def invalid(index: int) -> SessionPatternObservation:
    return SessionPatternObservation(
        session_index=index,
        valid_for_convergence=False,
        invalid_reason="baseline_rejected",
        holder_id=None,
        hue_degree=None,
        blink_bpm=None,
        exploration_decision=None,
        candidate_generated=False,
        candidate_accepted=False,
    )


def test_three_of_four_converges_and_latest_outlier_is_tolerated() -> None:
    evaluator = RollingConvergenceEvaluator(RollingConvergenceConfig())
    for item in (
        observed(0, 128.0, 118.0),
        observed(1, 129.0, 121.0),
        observed(2, 128.0, 120.0),
        observed(3, 4.0, 65.0, "life-red"),
    ):
        record = evaluator.update(item)
    assert record.currently_converged
    assert record.support_count == 3
    assert record.member_session_indices == (0, 1, 2)
    assert record.outlier_session_indices == (3,)
    assert record.latest_valid_session_is_outlier
    assert record.convergence_state == "converged_monitoring_latest_outlier"
    assert record.first_convergence_session_index == 3


def test_three_of_four_converges_when_the_oldest_session_is_the_outlier() -> None:
    records = evaluate_convergence_history(
        [
            observed(0, 7.0, 70.0, "life-red"),
            observed(1, 128.0, 118.0),
            observed(2, 129.0, 121.0),
            observed(3, 128.0, 120.0),
        ],
        RollingConvergenceConfig(),
    )
    final = records[-1]
    assert final.currently_converged
    assert final.member_session_indices == (1, 2, 3)
    assert final.outlier_session_indices == (0,)
    assert not final.latest_valid_session_is_outlier


def test_full_window_is_required_and_two_of_four_does_not_converge() -> None:
    config = RollingConvergenceConfig()
    three = evaluate_convergence_history(
        [observed(0), observed(1), observed(2)],
        config,
    )
    assert three[-1].convergence_state == "insufficient_valid_sessions"
    assert not three[-1].currently_converged
    four = evaluate_convergence_history(
        [
            observed(0),
            observed(1),
            observed(2, 10.0, 60.0, "life-red"),
            observed(3, 250.0, 140.0, "life-blue"),
        ],
        config,
    )
    assert four[-1].convergence_state == "searching"
    assert four[-1].support_count == 0


def test_four_of_four_selects_largest_subset_and_newest_duplicate_medoid() -> None:
    config = RollingConvergenceConfig()
    values = tuple(observed(index) for index in range(4))
    cluster = select_dominant_cluster(values, config)
    assert cluster is not None
    assert cluster.support_count == 4
    assert cluster.member_session_indices == (0, 1, 2, 3)
    assert cluster.maximum_pairwise_distance == 0.0
    assert cluster.mean_pairwise_distance == 0.0
    assert cluster.medoid_session_index == 3


def test_pairwise_complete_link_rejects_transitive_chain() -> None:
    config = RollingConvergenceConfig(window_sessions=3, required_sessions=3, maximum_sessions=3)
    # Adjacent pairs are within tolerance, but endpoints are two Hue tolerances apart.
    values = (
        observed(0, 100.0, 100.0),
        observed(1, 102.0, 100.0),
        observed(2, 104.0, 100.0),
    )
    assert select_dominant_cluster(values, config) is None


def test_equal_clusters_prefer_more_recent_sessions_before_holder_lexical() -> None:
    config = RollingConvergenceConfig(window_sessions=4, required_sessions=2)
    values = (
        observed(0, 7.0, 70.0, "life-red"),
        observed(1, 7.0, 70.0, "life-red"),
        observed(2, 252.0, 120.0, "life-blue"),
        observed(3, 252.0, 120.0, "life-blue"),
    )
    cluster = select_dominant_cluster(values, config)
    assert cluster is not None
    assert cluster.holder_id == "life-blue"
    assert cluster.member_session_indices == (2, 3)


def test_cluster_tie_break_prefers_maximum_distance_before_mean_and_recency() -> None:
    config = RollingConvergenceConfig(
        window_sessions=6,
        required_sessions=3,
        maximum_sessions=6,
    )
    values = (
        # Near-equilateral red cluster: max ~= mean ~= 0.8.
        observed(0, 100.0, 100.0, "life-red"),
        observed(1, 101.6, 100.0, "life-red"),
        observed(2, 100.8, 113.856406460551, "life-red"),
        # Newer blue cluster: max 0.9 but lower mean 0.6.
        observed(3, 250.0, 100.0, "life-blue"),
        observed(4, 250.0, 100.0, "life-blue"),
        observed(5, 251.8, 100.0, "life-blue"),
    )
    cluster = select_dominant_cluster(values, config)
    assert cluster is not None
    assert cluster.holder_id == "life-red"
    assert cluster.member_session_indices == (0, 1, 2)
    assert cluster.maximum_pairwise_distance == pytest.approx(0.8)
    assert cluster.mean_pairwise_distance == pytest.approx(0.8)


def test_invalid_sessions_are_history_but_not_valid_window_votes() -> None:
    config = RollingConvergenceConfig()
    records = evaluate_convergence_history(
        [observed(0), invalid(1), observed(2), observed(3), observed(4)],
        config,
    )
    assert records[3].convergence_state == "insufficient_valid_sessions"
    final = records[-1]
    assert final.currently_converged
    assert final.window_session_indices == (0, 2, 3, 4)
    assert final.valid_window_session_indices == (0, 2, 3, 4)
    assert 1 not in final.member_session_indices


def test_convergence_lost_and_reconvergence_are_counted_only_on_transitions() -> None:
    config = RollingConvergenceConfig()
    history = [
        observed(0),
        observed(1),
        observed(2),
        observed(3, 7.0, 70.0, "life-red"),
        observed(4, 7.0, 70.0, "life-red"),
        observed(5),
        observed(6),
        observed(7),
    ]
    records = evaluate_convergence_history(history, config)
    assert records[3].currently_converged
    assert records[4].convergence_state == "convergence_lost"
    assert records[4].convergence_lost_count == 1
    assert records[5].convergence_lost_count == 1
    assert records[7].currently_converged
    assert records[7].reconvergence_count == 1
    assert records[7].first_convergence_session_index == 3


def test_dominant_cluster_switch_is_counted_across_loss_and_reconvergence() -> None:
    records = evaluate_convergence_history(
        [
            observed(0),
            observed(1),
            observed(2),
            observed(3),
            observed(4, 7.0, 70.0, "life-red"),
            observed(5, 7.0, 70.0, "life-red"),
            observed(6, 7.0, 70.0, "life-red"),
        ],
        RollingConvergenceConfig(maximum_sessions=7),
    )
    assert records[5].convergence_state == "convergence_lost"
    assert records[6].holder_id == "life-red"
    assert records[6].reconvergence_count == 1
    assert records[6].dominant_cluster_switch_count == 1


def test_post_convergence_exploration_acceptance_and_outlier_return_counts() -> None:
    config = RollingConvergenceConfig()
    records = evaluate_convergence_history(
        [
            observed(0),
            observed(1),
            observed(2),
            observed(3),
            observed(4, 7.0, 70.0, "life-red", exploration="explore"),
            observed(5, exploration="explore", accepted=True),
        ],
        config,
    )
    final = records[-1]
    assert final.total_sessions_after_first_convergence == 2
    assert final.post_convergence_exploration_count == 2
    assert final.post_convergence_candidate_accepted_count == 1
    assert final.latest_outlier_count == 1
    assert final.outlier_return_within_one_session_count == 1
    assert final.outlier_return_within_two_sessions_count == 1


def test_config_and_record_json_are_canonical_strict_and_immutable() -> None:
    config = RollingConvergenceConfig()
    assert RollingConvergenceConfig.from_json(config.to_json()) == config
    assert config.to_json() == json.dumps(
        config.to_dict(),
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    values = config.to_dict()
    values.pop("window_sessions")
    with pytest.raises(ValueError, match="missing"):
        RollingConvergenceConfig.from_dict(values)
    with pytest.raises(ValueError, match="unknown"):
        RollingConvergenceConfig.from_dict({**config.to_dict(), "future": 1})
    with pytest.raises(ValueError, match="duplicate"):
        RollingConvergenceConfig.from_json('{"window_sessions":4,"window_sessions":4}')
    with pytest.raises(TypeError):
        RollingConvergenceConfig(window_sessions=True)
    with pytest.raises(ValueError):
        RollingConvergenceConfig(window_sessions=13)
    with pytest.raises(ValueError):
        RollingConvergenceConfig(hue_tolerance_degree=math.nan)
    with pytest.raises(ValueError, match="fixed to true"):
        RollingConvergenceConfig(use_valid_sessions_only=False)
    with pytest.raises(ValueError, match="fixed to true"):
        RollingConvergenceConfig(continue_after_convergence=False)

    record = evaluate_convergence_history(
        [observed(0), observed(1), observed(2), observed(3)],
        config,
    )[-1]
    assert RollingConvergenceRecord.from_json(record.to_json()) == record
    with pytest.raises(dataclasses.FrozenInstanceError):
        record.support_count = 0  # type: ignore[misc]
