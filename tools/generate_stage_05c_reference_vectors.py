#!/usr/bin/env python3
"""Generate production-independent Stage 5C relation-memory vectors."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any

SPEC_SIZE = 65_759
SPEC_SHA256 = "9707de5c07cbcb20603436b374f6a563b5d908206096f2a2204384ae91b22c73"
DOCUMENT_VERSION = "v2.0"
PROFILE_VERSION = "symbiotic_signal_loop_reference_v1_0"
ALGORITHM_VERSION = "adaptive_random_search_confirmed_v1"
STATE_SCHEMA_VERSION = "relation_memory_state_v2"
PROJECT_VERSION = "0.9.0"
MODEL_VERSION = "adaptive_relation_memory_connected_life_v0_1"
RELATION_UPDATE_POLICY_VERSION = "relation_update_effective_next_signal_v0_1"
BUNDLE1_REJECT_POLICY_VERSION = (
    "keep_same_trial_for_bundle2_but_require_two_valid_trial_evaluations_v0_1"
)
DIRECTION_FALLBACK_POLICY_VERSION = "positive_f_axis_on_near_zero_direction_norm_v0_1"
HASH01_DENOMINATOR = (1 << 48) - 1
DIRECTION_NORM_EPSILON = 1e-12
K_ANCHOR = (0.5, 0.5, 0.5, 0.5)
LIFE_IDS = ("life-red", "life-green", "life-blue")


def _hash01_entry(name: str, *parts: object) -> dict[str, Any]:
    joined = ":".join(str(part) for part in parts)
    encoded = joined.encode("utf-8")
    digest = hashlib.sha256(encoded).digest()
    numerator = int.from_bytes(digest[:6], byteorder="big", signed=False)
    value = numerator / HASH01_DENOMINATOR
    return {
        "name": name,
        "parts": list(parts),
        "joined_text": joined,
        "sha256_hex": digest.hex(),
        "prefix48_hex": digest[:6].hex(),
        "numerator": numerator,
        "denominator": HASH01_DENOMINATOR,
        "expected": value,
        "expected_binary64_hex": value.hex(),
    }


def _hash01(*parts: object) -> float:
    joined = ":".join(str(part) for part in parts).encode("utf-8")
    prefix = hashlib.sha256(joined).digest()[:6]
    return int.from_bytes(prefix, "big") / HASH01_DENOMINATOR


def _clip01(value: float) -> float:
    return min(1.0, max(0.0, value))


def _relation_search_radius(w: float) -> float:
    return _clip01(2.0 * w - 1.0)


def _intrinsic_profile(life_id: str) -> dict[str, Any]:
    curiosity = _hash01(life_id, "curiosity")
    return {
        "digital_life_id": life_id,
        "curiosity": curiosity,
        "sigma_min": 0.02 + 0.04 * curiosity,
        "sigma_max": 0.25 + 0.30 * curiosity,
        "epsilon_accept": 0.07 - 0.04 * curiosity,
        "p_explore_min": 0.10 + 0.20 * curiosity,
        "algorithm_version": ALGORITHM_VERSION,
    }


def _exploration_sigma(profile: dict[str, Any], w: float) -> float:
    radius = _relation_search_radius(w)
    return profile["sigma_min"] + (profile["sigma_max"] - profile["sigma_min"]) * (1.0 - radius)


def _exploration_probability(profile: dict[str, Any], w: float) -> float:
    radius = _relation_search_radius(w)
    return profile["p_explore_min"] + (1.0 - profile["p_explore_min"]) * (1.0 - radius)


def _reflect01(value: float) -> float:
    positive_modulo = value % 2.0
    return 1.0 - abs(1.0 - positive_modulo)


def _normalize_direction(u_f: float, u_t: float) -> tuple[float, tuple[float, ...]]:
    norm = math.hypot(u_f, u_t)
    if norm <= DIRECTION_NORM_EPSILON:
        return norm, (1.0, 0.0, 0.0, 0.0)
    return norm, (u_f / norm, 0.0, u_t / norm, 0.0)


def _direction(life_id: str, trial_index: int) -> dict[str, Any]:
    hash_f = _hash01(life_id, "C", "direction", trial_index, "F")
    hash_t = _hash01(life_id, "C", "direction", trial_index, "T")
    u_f = 2.0 * hash_f - 1.0
    u_t = 2.0 * hash_t - 1.0
    norm, xi = _normalize_direction(u_f, u_t)
    return {
        "digital_life_id": life_id,
        "trial_index_used": trial_index,
        "hash_f": hash_f,
        "hash_t": hash_t,
        "u_f": u_f,
        "u_t": u_t,
        "norm": norm,
        "xi": list(xi),
        "norm_epsilon": DIRECTION_NORM_EPSILON,
        "fallback_used": norm <= DIRECTION_NORM_EPSILON,
        "fallback_policy_version": DIRECTION_FALLBACK_POLICY_VERSION,
    }


def _candidate(
    k_anchor: tuple[float, float, float, float],
    sigma: float,
    xi: tuple[float, float, float, float],
) -> tuple[float, float, float, float]:
    return (
        _reflect01(k_anchor[0] + sigma * xi[0]),
        k_anchor[1],
        _reflect01(k_anchor[2] + sigma * xi[2]),
        k_anchor[3],
    )


def _find_hold_session_count(life_id: str, p_explore: float) -> int:
    for session_count in range(100_000):
        value = _hash01(life_id, "C", "explore", session_count)
        if value >= p_explore:
            return session_count
    raise RuntimeError("independent hold fixture search did not converge")


def _state_machine_fixture(
    *,
    name: str,
    profile: dict[str, Any],
    session_count: int = 0,
    g: int = 1,
    bundle0_valid: bool = True,
    w_anchor: float | None = 0.2,
    bundle1_valid: bool = True,
    w_trial_1: float | None = None,
    bundle2_valid: bool = True,
    w_bundle2: float | None = None,
) -> dict[str, Any]:
    """Evaluate the specified synthetic branch without using product code."""

    phase = "anchor_evaluation"
    adoption_result = "pending"
    exploration_decision: str | None = None
    sigma: float | None = None
    p_explore: float | None = None
    u_explore: float | None = None
    direction: dict[str, Any] | None = None
    k_trial: tuple[float, float, float, float] | None = None
    k_current = K_ANCHOR
    k_anchor = K_ANCHOR
    trial_count_before = 0
    trial_count_after = trial_count_before
    valid_trial_evaluation_count = 0
    anchor_return_w: float | None = None
    w_anchor_session: float | None = None
    provisional_condition: bool | None = None
    confirmation_condition_1: bool | None = None
    confirmation_condition_2: bool | None = None
    candidate_mean_w: float | None = None
    rollback_reason: str | None = None
    candidate_effective_signal_index: int | None = None
    k_anchor_update_count = 0
    presented_bundle0 = K_ANCHOR
    if g == 0:
        phase_after_bundle0 = "completed_non_holder"
        phase = phase_after_bundle0
        adoption_result = "non_holder_no_adaptation"
    elif not bundle0_valid:
        phase_after_bundle0 = "hold"
        phase = phase_after_bundle0
        adoption_result = "bundle0_evaluation_rejected"
    else:
        if w_anchor is None:
            raise ValueError("valid Bundle 0 fixture requires W")
        w_anchor_session = w_anchor
        sigma = _exploration_sigma(profile, w_anchor)
        p_explore = _exploration_probability(profile, w_anchor)
        u_explore = _hash01(profile["digital_life_id"], "C", "explore", session_count)
        exploration_decision = "explore" if u_explore < p_explore else "hold"
        if exploration_decision == "hold":
            phase = "hold"
            adoption_result = "hold"
        else:
            direction = _direction(profile["digital_life_id"], trial_count_before)
            xi = tuple(direction["xi"])
            k_trial = _candidate(K_ANCHOR, sigma, xi)  # type: ignore[arg-type]
            k_current = k_trial
            trial_count_after += 1
            candidate_effective_signal_index = 121
            phase = "trial"
        phase_after_bundle0 = phase

    presented_bundle1 = k_current
    if phase == "trial":
        if bundle1_valid:
            if w_trial_1 is None or w_anchor_session is None:
                raise ValueError("valid Bundle 1 fixture requires W values")
            valid_trial_evaluation_count = 1
            provisional_condition = w_trial_1 > (w_anchor_session + profile["epsilon_accept"])
            if provisional_condition:
                phase = "confirmation"
            else:
                phase = "return_anchor"
                adoption_result = "rejected_bundle1_threshold"
                k_current = K_ANCHOR
        else:
            phase = "trial_unconfirmed"
            adoption_result = "unconfirmed_evaluation_reject"
    phase_after_bundle1 = phase

    presented_bundle2 = k_current
    if phase == "confirmation":
        if bundle2_valid:
            if w_bundle2 is None or w_trial_1 is None or w_anchor_session is None:
                raise ValueError("valid confirmation fixture requires all W values")
            valid_trial_evaluation_count = 2
            candidate_mean_w = (w_trial_1 + w_bundle2) / 2.0
            confirmation_condition_1 = w_bundle2 > w_anchor_session
            confirmation_condition_2 = candidate_mean_w > (
                w_anchor_session + profile["epsilon_accept"]
            )
            if confirmation_condition_1 and confirmation_condition_2:
                if k_trial is None:
                    raise RuntimeError("confirmation has no candidate")
                k_anchor = k_trial
                k_current = k_trial
                phase = "accepted"
                adoption_result = "accepted"
                k_anchor_update_count = 1
            else:
                k_current = K_ANCHOR
                phase = "rejected"
                adoption_result = "rejected_after_confirmation"
                rollback_reason = "confirmation_conditions_not_met"
        else:
            k_current = K_ANCHOR
            phase = "rejected"
            adoption_result = "unconfirmed_evaluation_reject"
            rollback_reason = "bundle2_evaluation_rejected"
    elif phase == "return_anchor":
        k_current = K_ANCHOR
        if bundle2_valid:
            anchor_return_w = w_bundle2
            w_anchor_session = anchor_return_w
        else:
            rollback_reason = "return_anchor_evaluation_rejected"
    elif phase == "trial_unconfirmed":
        if bundle2_valid and w_bundle2 is not None:
            valid_trial_evaluation_count = 1
        k_current = K_ANCHOR
        phase = "rejected"
        adoption_result = "unconfirmed_evaluation_reject"
        rollback_reason = "fewer_than_two_valid_trial_evaluations"
    phase_after_bundle2 = phase

    unresolved_candidate = k_trial is not None and adoption_result not in {
        "accepted",
        "rejected_after_confirmation",
        "rejected_bundle1_threshold",
        "unconfirmed_evaluation_reject",
    }
    if unresolved_candidate:
        k_current = K_ANCHOR
        adoption_result = "rolled_back_at_session_end"
        rollback_reason = "unresolved_candidate_at_session_end"
    if phase == "completed_non_holder":
        final_phase = "completed_non_holder"
    elif adoption_result == "bundle0_evaluation_rejected":
        final_phase = "completed_bundle0_rejected"
    else:
        final_phase = phase

    return {
        "name": name,
        "inputs": {
            "g": g,
            "bundle0_valid": bundle0_valid,
            "W_anchor": w_anchor,
            "bundle1_valid": bundle1_valid,
            "W_trial_1": w_trial_1,
            "bundle2_valid": bundle2_valid,
            "W_bundle2": w_bundle2,
        },
        "session_count_used": session_count,
        "session_count_after_closing": session_count + 1,
        "trial_count_before": trial_count_before,
        "trial_count_after": trial_count_after,
        "exploration_decision": exploration_decision,
        "sigma": sigma,
        "p_explore": p_explore,
        "u_explore": u_explore,
        "direction": direction,
        "candidate_generated": k_trial is not None,
        "candidate_generation_count": int(k_trial is not None),
        "candidate_generation_trial_index": (
            None if direction is None else direction["trial_index_used"]
        ),
        "candidate_effective_signal_index": candidate_effective_signal_index,
        "presented_k_by_bundle": {
            "bundle_0": list(presented_bundle0),
            "bundle_1": list(presented_bundle1),
            "bundle_2": list(presented_bundle2),
        },
        "phase_after_bundle_0": phase_after_bundle0,
        "phase_after_bundle_1": phase_after_bundle1,
        "phase_after_bundle_2": phase_after_bundle2,
        "phase_after_closing": final_phase,
        "provisional_condition": provisional_condition,
        "confirmation_condition_1": confirmation_condition_1,
        "confirmation_condition_2": confirmation_condition_2,
        "candidate_mean_W": candidate_mean_w,
        "valid_trial_evaluation_count": valid_trial_evaluation_count,
        "anchor_return_W": anchor_return_w,
        "W_anchor_session_after": w_anchor_session,
        "adoption_result": adoption_result,
        "rollback_reason": rollback_reason,
        "initial_k_anchor": list(K_ANCHOR),
        "candidate_audit_k_trial": None if k_trial is None else list(k_trial),
        "active_k_trial_after_closing": None,
        "final_k_current": list(k_current),
        "final_k_anchor": list(k_anchor),
        "k_anchor_update_count": k_anchor_update_count,
        "session_finalized": True,
    }


def _branch_vectors(profile: dict[str, Any]) -> list[dict[str, Any]]:
    epsilon = profile["epsilon_accept"]
    hold_count = _find_hold_session_count(profile["digital_life_id"], profile["p_explore_min"])
    return [
        _state_machine_fixture(
            name="hold",
            profile=profile,
            session_count=hold_count,
            w_anchor=1.0,
        ),
        _state_machine_fixture(
            name="accepted",
            profile=profile,
            w_anchor=0.2,
            w_trial_1=0.2 + epsilon + 0.08,
            w_bundle2=0.2 + epsilon + 0.06,
        ),
        _state_machine_fixture(
            name="bundle1_threshold_fail",
            profile=profile,
            w_anchor=0.4,
            w_trial_1=0.4 + epsilon,
            w_bundle2=0.42,
        ),
        _state_machine_fixture(
            name="confirmation_condition1_fail",
            profile=profile,
            w_anchor=0.4,
            w_trial_1=0.4 + epsilon + 0.08,
            w_bundle2=0.4,
        ),
        _state_machine_fixture(
            name="confirmation_mean_fail",
            profile=profile,
            w_anchor=0.4,
            w_trial_1=0.4 + epsilon + 0.01,
            w_bundle2=0.401,
        ),
        _state_machine_fixture(
            name="bundle0_evaluation_reject",
            profile=profile,
            bundle0_valid=False,
            w_anchor=None,
        ),
        _state_machine_fixture(
            name="bundle1_evaluation_reject",
            profile=profile,
            w_anchor=0.2,
            bundle1_valid=False,
            w_trial_1=None,
            bundle2_valid=True,
            w_bundle2=0.35,
        ),
        _state_machine_fixture(
            name="bundle2_evaluation_reject",
            profile=profile,
            w_anchor=0.2,
            w_trial_1=0.2 + epsilon + 0.08,
            bundle2_valid=False,
            w_bundle2=None,
        ),
        _state_machine_fixture(
            name="g_zero",
            profile=profile,
            g=0,
            w_anchor=0.2,
        ),
        _state_machine_fixture(
            name="incremental_improvement_below_neutral",
            profile=profile,
            w_anchor=0.2,
            w_trial_1=0.2 + epsilon + 0.04,
            w_bundle2=0.2 + epsilon + 0.03,
        ),
    ]


def _pre_stage5c_regression() -> dict[str, Any]:
    """Return the immutable baseline captured at commit c10d554."""

    return {
        "baseline_commit": "c10d55460d4c9ec009397ec62a8a81f20cfaecc7",
        "headless_digests": {
            "stage_1": {
                "deterministic": "1c4217065fa29316e7ead83c4d604e87f9fe8fe46e82b689b5566dbc9890598d"
            },
            "stage_2": {
                "heartbeat": "4c039f5f1b5cc3cd78682cca890a8a6ec70510a52b4ad4addeabcb0ecd3ae765",
                "diagnostic": "ef0bc8c644e8b5f6fc2c3b58ef825491e49e005bc0c6c22a9f0c62c66168cd8f",
                "full_event": "761a2dc6b2b03c4d538a85d95160f2ecc731e301a1362006ee97ea575872bddb",
            },
            "stage_3": {
                "heartbeat": "4c039f5f1b5cc3cd78682cca890a8a6ec70510a52b4ad4addeabcb0ecd3ae765",
                "rri_measurement": (
                    "69d645f9e742f8cb9dbb16d9deb65ff10ce77b31c66c35e8fd01cfc5c97272b3"
                ),
                "full_event": "d5a174f007a160a1442569b017fe404806db61cc18e0b6a0cda99cd2995b6572",
            },
            "stage_4": {
                "artifact": "4bea74309fcc62922325bd94a6a6a8561daf63740a4fe1b853c9a26f3b6838f1",
                "evaluation": "371f7d7618b8dbc1259f17765409fed1167eaa8fd4bdf62bef743891b726dd1e",
                "signal": "0f68cde436e712e7dad5608ad6347af216cee80945ca951404cf511825785add",
                "full_event": "34b18fa72f51cd5cccf9ef7107000d0ef2fdeeb4f62c3e8d7f0ae3de1cd19b72",
            },
            "stage_5a": {
                "first_round": "661c2c74942d6b217a635fb4f2cb142bee8cff2e0e842cd21ccdd511682028b8",
                "evaluation_update": (
                    "f7bf973cc20a2af77ccd7b38fa0e2407801353890a23cc1b3e30e9d7feeba4c3"
                ),
                "full_event": "34b18fa72f51cd5cccf9ef7107000d0ef2fdeeb4f62c3e8d7f0ae3de1cd19b72",
            },
            "stage_5b1": {
                "touch": "0d5f8671fd3859f74be7c758954952c8976eb02dcea62b7074ec459063a76c75",
                "qualification": "1dd880f811bf1dd6e56e2842a65d565aa82c7e4fb61cbb4a5b2f123946102eed",
                "qualified_b": "6157d8251af0e0ceb784b664d90d01368b8506efeb37665962244f991b6a57b7",
                "feedback": "121c9bfdee73a3411864829f146958afc134fc2b08d96c70a71f20d11fc0ff62",
                "second_round_by_life": {
                    "life-blue": (
                        "d299790089141d8285c1de9fcf8e7ce2756f91e2ed3535ab3340d544412866b6"
                    ),
                    "life-green": (
                        "cf7ed41be629cc6a7bd9f054c6f2758332facdf31d381acf970a3b4da6e8ebdc"
                    ),
                    "life-red": (
                        "d299790089141d8285c1de9fcf8e7ce2756f91e2ed3535ab3340d544412866b6"
                    ),
                },
                "full_event": "fa68733a98a962fcad7aeb58d7ec12439e860d8d02c43beaae42e345d5a0884f",
            },
            "stage_6": {
                "command": "306648650d4b286a48b3f9188f7fd640764b05fb135c581c4b9d00b487d06020",
                "stimulus_state": (
                    "1dbf214e1448802a665031f73fb798cdbf04471210aeddf438c68b72b616265e"
                ),
                "segment": "9dabc1b018b52f9be603ba164655f3c5fa79ff4f6579ae8a6bfd48047d8fd763",
                "waveform_sample": (
                    "a075f488a588d7d2f78548e4ae339e7cac59c88f8e4508b2a89f0ca6e36cc0c0"
                ),
                "full_event": "f2ef166cd2bbea252d2c848b7f67d80cad1840534fe736d792087639b5b2a833",
            },
            "stage_71_aligned": {
                "heartbeat": "3392698943c200a9ab08964644ca72d56f50dfc1944c225b8c3e7933c5a229ae",
                "responsive": "f8240cabbc882ceef81b537c29f907b60c23bad3bc207dac3c4a51b52aaca3cd",
                "light_receipt": "8d46a403067232d1d4532ba878d22881ddc2e5f5b7e429394b5d26b02a03e706",
                "physical_audit_segment": (
                    "b09c15e82e25ee42eaaea0d374ac7ba041494f59c742fb953ec178a31f5ffe85"
                ),
                "response_dynamics_epoch": (
                    "d1be764aa7ffa60a8545e03e7f1fc853a4a95291a95dad09b873d1b9e2a31916"
                ),
                "response_sample": (
                    "b230c3d38ca3d1f85ba910c5970f667970c8d6e66533c84b3ecca7abe7c30bb7"
                ),
                "full_event": "db9948271c0a664cd990c9954b131ebefc855a553005225241a6f94ac00625bf",
            },
            "stage_71_off_center": {
                "heartbeat": "d841f8243bcb839ab7e26f00fcaeedcf307b12c51af26667d313aa57b2e2b7f7",
                "responsive": "ca77c5bd92050c42aedd8896cfc8c4e49f252f395fadba862594b1fe8834680f",
                "light_receipt": "45167f62c4cd6723f953a63d8e25de1f60215770571dcd4d54928f01f39e17f4",
                "physical_audit_segment": (
                    "f764fcbcc6a4e5bba0db9b080c8056bcaedd49a0a12ac573953593b40f4e4647"
                ),
                "response_dynamics_epoch": (
                    "2afb235b6b41b98fd6a34dd1dcc3b1e2365ed93d26e27ee76e71f0cb71689de1"
                ),
                "response_sample": (
                    "603193f2096b53bcca280df1ea2cde1acfe7574a7ee4abc91aefbca30f941116"
                ),
                "full_event": "97289a7bd4672edb5ffc7ecb56543a7602638c1a9b76a0859b81bbef332c67d2",
            },
            "stage_71_control": {
                "heartbeat": "dfc32d05a372482a81a40ffbb9dc721aed8edcada4709a4dcb86e76719ddf17b",
                "responsive": "d36e2f696be6e4bd0c4149a4428e0f2804d8647856c8d964379bf22930c2ef98",
                "light_receipt": "b04fc7a895bbd9ebb42787203ff38d3bfed5db41dbd389425ce81b3326241941",
                "physical_audit_segment": (
                    "b09c15e82e25ee42eaaea0d374ac7ba041494f59c742fb953ec178a31f5ffe85"
                ),
                "response_dynamics_epoch": (
                    "d1be764aa7ffa60a8545e03e7f1fc853a4a95291a95dad09b873d1b9e2a31916"
                ),
                "response_sample": (
                    "ae7baba6557d6a3d763c5933a1be1974c7a5990cd8e598ba48eed423c6837351"
                ),
                "full_event": "f2ef166cd2bbea252d2c848b7f67d80cad1840534fe736d792087639b5b2a833",
            },
        },
        "csv_byte_regression": {
            "stage4/garden_input_evaluations.csv": [
                755,
                "e54567bf2257bdf90856b9e8acce5b389e005cdc4ef729b3b71f99a9f9d19865",
            ],
            "stage4/garden_input_rri_classification_diagnostics.csv": [
                55_216,
                "7caa4953887d3dee9b9dbb1ad8ae992a0f5c12ac190cdac24ba1d022985618fc",
            ],
            "stage4/garden_input_signals.csv": [
                28_376,
                "b694fd74137540e7b6a90563c5a8f5cfa95dc6595ccaaf61220bb03701b7bd17",
            ],
            "stage5a/single_digital_life_evaluation_updates.csv": [
                772,
                "1983f408976411aa2af23bba00b3ab7562e4a31917c18395d446555bc9919b08",
            ],
            "stage5a/single_digital_life_first_round_diagnostics.csv": [
                70_966,
                "10cf8d4b77b6a1f74ed4b5a0fe092c4bbc608276ea94dd9173cac3197faf63ac",
            ],
            "stage5b1/stage_05b_digital_life_second_round.csv": [
                112_343,
                "f856cf9641ee40fe01a66b6971b1798aa5cd1c9b2284aa992ac4e0b297b242b7",
            ],
            "stage5b1/stage_05b_digital_life_touches.csv": [
                97_369,
                "f312dfa6d8d84ff0d522b3d60702e5fbeb42ace41cb9844c4c853a1ad6df5594",
            ],
            "stage5b1/stage_05b_garden_qualification.csv": [
                28_422,
                "15da2507ad4d25d84a0331e6c8c0894b05f26cd2cda5d2e7688004ca082c7273",
            ],
            "stage5b1/stage_05b_qualified_b_outputs.csv": [
                30_118,
                "716f62f6c4434107c015ab60468c85f25d8d297937f27c99ec4b4b4f8a78bdfa",
            ],
            "stage6/stage_06_light_commands.csv": [
                64_035,
                "907becf1caeaf401e3aabc5a8965e20a1ae59025be10a0b19730827455be7a13",
            ],
            "stage6/stage_06_light_stimulus_segments.csv": [
                43_848,
                "84ddf3f2552a8d04ad07b00139df4c413eeb766b1d688221140b05ce762c5a83",
            ],
            "stage6/stage_06_light_stimulus_states.csv": [
                31_686,
                "bca483113914b3f57f9e81dc2452b8d2457979a5d89ac501b73f9609d3759dd0",
            ],
            "stage6/stage_06_light_waveform_samples_20ms.csv": [
                1_041_344,
                "0f23368bb7d5807954dbf3b54d71ce8accc04a312c66bfdbf733ca8ccb94f486",
            ],
            "stage71-aligned/stage_07_light_response_samples_100ms.csv": [
                216_910,
                "27ea0e83d784d86e0d9898765a1a35165d32f5f0fae89b9c0a9bb519d47bc171",
            ],
            "stage71-aligned/stage_07_light_response_segments.csv": [
                1_152,
                "1643f75f26c9b1c36a8851062fec9dec82b6d612a172f341cf81a4b329d9436a",
            ],
            "stage71-aligned/stage_07_light_responsive_heartbeats.csv": [
                100_456,
                "f3ef4dd27a529f79b992c917f358e4a508404dd1ffc7463113d91645f6e23714",
            ],
            "stage71-aligned/stage_07_light_stimulus_receipts.csv": [
                88_061,
                "ef9530eb20b375e3ad01013298794857c2721562cae969e0d35edfb0c662905e",
            ],
            "stage71-aligned/stage_07_response_dynamics_epochs.csv": [
                428,
                "8517429b7646dded46e4e815eddca389838beb1a6eb5df51ec2d09657cb20af4",
            ],
            "stage71-control/stage_07_light_response_samples_100ms.csv": [
                194_011,
                "6fc2b17fd9cf19f9891aaaee31ff4ad79e9dca508d7a9991d946ffed21daf19a",
            ],
            "stage71-control/stage_07_light_response_segments.csv": [
                1_152,
                "1643f75f26c9b1c36a8851062fec9dec82b6d612a172f341cf81a4b329d9436a",
            ],
            "stage71-control/stage_07_light_responsive_heartbeats.csv": [
                92_839,
                "20fbbb4d81611355451e1e92eacde5f07739f75dab1a0e38ef27be5ad6d06c88",
            ],
            "stage71-control/stage_07_light_stimulus_receipts.csv": [
                88_050,
                "761d01015e32d9060824e3aac4a6b2c7be366c46e994eab3e49ea47784d072ce",
            ],
            "stage71-control/stage_07_response_dynamics_epochs.csv": [
                428,
                "8517429b7646dded46e4e815eddca389838beb1a6eb5df51ec2d09657cb20af4",
            ],
            "stage71-offcenter/stage_07_light_response_samples_100ms.csv": [
                275_851,
                "8f10a235cc97dec8985ccfe7ad318274bf914098fc55abc327e43196e344dd8f",
            ],
            "stage71-offcenter/stage_07_light_response_segments.csv": [
                1_215,
                "195f4ab121601689b7b8a6c35acf7bfe7e4606612c163860985382ede3391e37",
            ],
            "stage71-offcenter/stage_07_light_responsive_heartbeats.csv": [
                107_656,
                "f1f8de012e67e2205a51f850cba5dea7b2d0e28c561b92fd1d4d9d758fb3e107",
            ],
            "stage71-offcenter/stage_07_light_stimulus_receipts.csv": [
                99_586,
                "0a0965b5ebe560bbc5f53d2f72da0ce8eeabdc714ee1a1a4cfb4e8ec56fa4886",
            ],
            "stage71-offcenter/stage_07_response_dynamics_epochs.csv": [
                444,
                "0c3406182fd8350f4ba8f5104f5a15fb97592164d069a491e68f5df4b97c90ec",
            ],
        },
    }


def build_reference_vectors() -> dict[str, Any]:
    profiles = [_intrinsic_profile(life_id) for life_id in LIFE_IDS]
    green = next(profile for profile in profiles if profile["digital_life_id"] == "life-green")
    curiosity_hashes = [
        _hash01_entry(f"{life_id}_curiosity", life_id, "curiosity") for life_id in LIFE_IDS
    ]
    explore_hashes = [
        _hash01_entry(
            f"{life_id}_explore_session_{session_count}",
            life_id,
            "C",
            "explore",
            session_count,
        )
        for life_id in LIFE_IDS
        for session_count in (0, 1)
    ]
    direction_hashes = [
        _hash01_entry(
            f"{life_id}_direction_trial_{trial_index}_{axis}",
            life_id,
            "C",
            "direction",
            trial_index,
            axis,
        )
        for life_id in LIFE_IDS
        for trial_index in (0, 1)
        for axis in ("F", "T")
    ]
    radius_vectors = [
        {"W_anchor_session": w, "expected": _relation_search_radius(w)}
        for w in (0.0, 0.5, 0.75, 1.0)
    ]
    width_probability_vectors = [
        {
            "digital_life_id": green["digital_life_id"],
            "W_anchor_session": w,
            "r": _relation_search_radius(w),
            "sigma": _exploration_sigma(green, w),
            "p_explore": _exploration_probability(green, w),
        }
        for w in (0.0, 0.5, 0.75, 1.0)
    ]
    reflect_inputs = (0.0, 0.8, 1.0, 1.2, -0.2, 2.2)
    reflect_vectors = [
        {
            "input": value,
            "expected": _reflect01(value),
            "expected_binary64_hex": _reflect01(value).hex(),
        }
        for value in reflect_inputs
    ]
    reflect_vector_input = (-0.2, 0.8, 1.2, 2.2)
    directions = [
        _direction(life_id, trial_index) for life_id in LIFE_IDS for trial_index in (0, 1)
    ]
    candidate_direction = _direction("life-green", 0)
    candidate_sigma = _exploration_sigma(green, 0.2)
    candidate_anchor = (0.92, 0.37, 0.08, 0.64)
    candidate_xi = tuple(candidate_direction["xi"])
    generated_candidate = _candidate(  # type: ignore[arg-type]
        candidate_anchor,
        candidate_sigma,
        candidate_xi,
    )
    equality_anchor = 0.5
    equality_epsilon = 0.0625
    equality_threshold = equality_anchor + equality_epsilon
    mean_equality_w1 = 0.59375
    mean_equality_w2 = 0.53125
    branch_vectors = _branch_vectors(green)

    return {
        "schema_version": "stage_05c_reference_vectors_v1",
        "normative_source": {
            "document_version": DOCUMENT_VERSION,
            "profile_version": PROFILE_VERSION,
            "algorithm_version": ALGORITHM_VERSION,
            "state_schema_version": STATE_SCHEMA_VERSION,
            "size_bytes": SPEC_SIZE,
            "sha256": SPEC_SHA256,
            "directly_read_sections": [25, 26, 27],
        },
        "simulation_assumptions": {
            "project_version": PROJECT_VERSION,
            "adaptive_life_model_version": MODEL_VERSION,
            "relation_update_effective_policy_version": (RELATION_UPDATE_POLICY_VERSION),
            "bundle1_reject_policy_version": BUNDLE1_REJECT_POLICY_VERSION,
            "direction_fallback_policy_version": (DIRECTION_FALLBACK_POLICY_VERSION),
            "direction_norm_epsilon": DIRECTION_NORM_EPSILON,
            "single_session_only": True,
            "convergence_evaluated": False,
            "multi_session_not_implemented": True,
        },
        "canonical_digest_contract": {
            "encoding": "UTF-8",
            "sort_keys": True,
            "allow_nan": False,
            "separators": [",", ":"],
            "digest_names": [
                "intrinsic_profile_digest",
                "adaptive_signal_digest",
                "relation_memory_transition_digest",
                "final_persistent_state_digest",
                "session_summary_digest",
            ],
        },
        "hash01": {
            "join_policy": "colon_joined_str_parts_utf8",
            "hash": "SHA-256",
            "prefix_bits": 48,
            "denominator": HASH01_DENOMINATOR,
            "curiosity": curiosity_hashes,
            "explore": explore_hashes,
            "direction": direction_hashes,
        },
        "intrinsic_profiles": profiles,
        "relation_search_radius": radius_vectors,
        "sigma_and_probability": width_probability_vectors,
        "strict_exploration_decision": [
            {"u_explore": 0.499999999999, "p_explore": 0.5, "expected": "explore"},
            {"u_explore": 0.5, "p_explore": 0.5, "expected": "hold"},
            {"u_explore": 0.500000000001, "p_explore": 0.5, "expected": "hold"},
        ],
        "reflect01": {
            "formula": "1-abs(1-mod_positive(x,2))",
            "scalar_vectors": reflect_vectors,
            "vector": {
                "input": list(reflect_vector_input),
                "expected": [_reflect01(value) for value in reflect_vector_input],
            },
            "is_not_clip": True,
        },
        "direction": {
            "uses_pre_increment_trial_count": True,
            "vectors": directions,
            "fallback": {
                "u_f": 0.0,
                "u_t": 0.0,
                "norm": 0.0,
                "xi": [1.0, 0.0, 0.0, 0.0],
                "policy_version": DIRECTION_FALLBACK_POLICY_VERSION,
            },
        },
        "candidate": {
            "digital_life_id": "life-green",
            "trial_count_before": 0,
            "trial_index_used": 0,
            "trial_count_after": 1,
            "W_anchor_session": 0.2,
            "sigma": candidate_sigma,
            "direction_xi": list(candidate_xi),
            "k_anchor": list(candidate_anchor),
            "raw_f": candidate_anchor[0] + candidate_sigma * candidate_xi[0],
            "raw_t": candidate_anchor[2] + candidate_sigma * candidate_xi[2],
            "k_trial": list(generated_candidate),
            "a_unchanged": generated_candidate[1] == candidate_anchor[1],
            "d_unchanged": generated_candidate[3] == candidate_anchor[3],
            "k_anchor_changed_during_generation": False,
            "candidate_count": 1,
            "continuous_no_grid_rounding": True,
        },
        "strict_thresholds": {
            "anchor": equality_anchor,
            "epsilon_accept": equality_epsilon,
            "provisional": [
                {
                    "W_trial_1": equality_threshold,
                    "expected": False,
                    "reason": "equality_fails_strict_greater_than",
                },
                {
                    "W_trial_1": math.nextafter(equality_threshold, math.inf),
                    "expected": True,
                },
            ],
            "confirmation_condition_1": [
                {"W_trial_2": equality_anchor, "expected": False},
                {
                    "W_trial_2": math.nextafter(equality_anchor, math.inf),
                    "expected": True,
                },
            ],
            "confirmation_condition_2": {
                "W_trial_1": mean_equality_w1,
                "W_trial_2": mean_equality_w2,
                "mean": (mean_equality_w1 + mean_equality_w2) / 2.0,
                "threshold": equality_threshold,
                "expected": False,
                "reason": "mean_equality_fails_strict_greater_than",
            },
            "incremental_improvement": {
                "W_anchor": 0.2,
                "epsilon_accept": 0.05,
                "W_trial_1": 0.30,
                "W_trial_2": 0.29,
                "mean": 0.295,
                "accepted": True,
                "absolute_level_below_neutral": True,
            },
        },
        "counter_and_timing_policy": {
            "trial_count_increment": "candidate_generation_only",
            "session_count_increment": "successful_closing_second_round_only",
            "explore_hash_uses_session_count_before_closing": True,
            "direction_hash_uses_trial_count_before_generation": True,
            "candidate_generated_at_signal": 120,
            "candidate_first_presented_at_signal": 121,
            "bundle1_decision_at_signal": 180,
            "bundle2_selection_first_presented_at_signal": 181,
            "final_decision_at_signal": 240,
            "same_signal_b_recomputed_after_relation_update": False,
            "policy_version": RELATION_UPDATE_POLICY_VERSION,
        },
        "state_machine_branches": branch_vectors,
        "pre_stage5c_regression": _pre_stage5c_regression(),
    }


def _encoded_vectors() -> str:
    return (
        json.dumps(
            build_reference_vectors(),
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    default_output = project_root / "docs" / "conformance" / "stage-05c-reference-vectors.json"
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=default_output)
    parser.add_argument("--stdout", action="store_true")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    encoded = _encoded_vectors()
    if args.stdout:
        sys.stdout.write(encoded)
        return 0
    if args.check:
        if not args.output.exists():
            return 1
        return int(args.output.read_text(encoding="utf-8") != encoded)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
