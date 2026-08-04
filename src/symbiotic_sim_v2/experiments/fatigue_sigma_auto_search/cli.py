"""Headless command adapter for the offline Stage 8A.2 search."""

from __future__ import annotations

import json
import signal
from dataclasses import replace
from pathlib import Path
from typing import Any

from .config import AutoSearchConfig, CandidateGateConfig
from .job import canonical_json
from .plan import build_search_plan
from .runner import AutoSearchRunner


def _load_gate(path: Path | None) -> CandidateGateConfig | None:
    if path is None:
        return None
    if not path.is_file():
        raise ValueError(f"candidate gate config does not exist: {path}")
    return CandidateGateConfig.from_json(path.read_text(encoding="utf-8"))


def _config_from_args(args: Any) -> AutoSearchConfig:
    gate = _load_gate(args.candidate_gate_config)
    if args.search_config is not None:
        if not args.search_config.is_file():
            raise ValueError(f"search config does not exist: {args.search_config}")
        config = AutoSearchConfig.from_json(args.search_config.read_text(encoding="utf-8"))
        if gate is not None:
            config = replace(config, candidate_gate_config=gate)
        return config
    preset = args.search_preset or "standard"
    return AutoSearchConfig.create(
        search_preset=preset,
        base_master_seed=(20260802 if args.base_master_seed is None else args.base_master_seed),
        include_reference_arm=(
            False if args.include_reference_arm is None else args.include_reference_arm
        ),
        output_directory=(
            "artifacts/auto_search" if args.output_directory is None else str(args.output_directory)
        ),
        maximum_total_session_runs=args.maximum_total_session_runs,
        stop_after_phase=args.stop_after_phase,
        retain_full_details_policy=(
            "phase3_full" if args.retain_full_details is None else args.retain_full_details
        ),
        candidate_gate_config=gate,
    )


def plan_only_projection(config: AutoSearchConfig) -> dict[str, Any]:
    plan = build_search_plan(config)
    return {
        "mode": "plan_only",
        "config": config.to_dict(),
        "plan": plan.to_dict(),
        "conditions": sum(phase.maximum_condition_count for phase in plan.phases),
        "user_types": len(config.user_type_ids),
        "reference_jobs": (
            0
            if not config.include_reference_arm
            else sum(len(phase.user_type_ids) * phase.replicate_count for phase in plan.phases)
        ),
        "total_planned_session_runs": plan.maximum_planned_session_runs,
        "reference_session_runs": plan.reference_session_runs,
        "simulation_jobs_executed": 0,
        "state_changed": False,
    }


def _progress(payload: dict[str, Any]) -> None:
    print(canonical_json({"progress": payload}), flush=True)


def run_auto_search_cli(args: Any, *, repo_root: Path | None = None) -> int:
    if args.resume is not None:
        if args.plan_only:
            raise ValueError("--plan-only cannot be combined with --resume")
        resume_conflicts = (
            args.search_preset,
            args.output_directory,
            args.base_master_seed,
            args.include_reference_arm,
            args.stop_after_phase,
            args.maximum_total_session_runs,
            args.candidate_gate_config,
            args.search_config,
            args.retain_full_details,
        )
        if any(value is not None for value in resume_conflicts):
            raise ValueError("new-run search options cannot be combined with --resume")
        if not args.resume.is_dir():
            raise ValueError(f"resume directory does not exist: {args.resume}")
        runner = AutoSearchRunner(
            repo_root=repo_root,
            resume_directory=args.resume,
            progress_callback=_progress,
            allow_dirty_code=args.allow_dirty_auto_search_code,
        )
    else:
        config = _config_from_args(args)
        if args.plan_only:
            print(
                json.dumps(
                    plan_only_projection(config),
                    allow_nan=False,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        runner = AutoSearchRunner(
            config,
            repo_root=repo_root,
            progress_callback=_progress,
            allow_dirty_code=args.allow_dirty_auto_search_code,
        )
    signal_count = 0
    previous_handlers: dict[signal.Signals, Any] = {}

    def handle_signal(signum: int, _frame: Any) -> None:
        nonlocal signal_count
        signal_count += 1
        if signal_count == 1:
            runner.request_cancel()
            print(
                canonical_json(
                    {
                        "cancellation": "graceful_requested",
                        "signal": signal.Signals(signum).name,
                    }
                ),
                flush=True,
            )
        else:
            runner.request_cancel(immediate=True)
            raise KeyboardInterrupt

    for selected_signal in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[selected_signal] = signal.getsignal(selected_signal)
        signal.signal(selected_signal, handle_signal)
    try:
        summary = runner.run()
    except KeyboardInterrupt:
        print(
            canonical_json(
                {
                    "status": "interrupted",
                    "run_directory": str(runner.run_directory),
                    "checkpoint": str(runner.run_directory / "checkpoint.json"),
                }
            ),
            flush=True,
        )
        return 130
    finally:
        for selected_signal, previous in previous_handlers.items():
            signal.signal(selected_signal, previous)
    print(
        json.dumps(
            summary.to_dict(),
            allow_nan=False,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if summary.status in {"completed", "cancelled"} else 1


__all__ = ["plan_only_projection", "run_auto_search_cli"]
