"""Headless CLI adapter for Stage 8A.3.1 local factorial validation."""

from __future__ import annotations

import json
import signal
from pathlib import Path
from typing import Any

from symbiotic_sim_v2.experiments.adaptive_placebo_validation.config import (
    DEFAULT_BASE_MASTER_SEED,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.job import canonical_json

from .config import FactorialValidationConfig, factorial_plan_projection
from .runner import FatigueRecoverySigmaFactorialRunner


def _config_from_args(args: Any) -> FactorialValidationConfig:
    return FactorialValidationConfig.create(
        validation_preset=args.validation_preset or "standard",
        participants_per_type=args.participants_per_type,
        maximum_sessions=args.maximum_sessions,
        base_master_seed=(
            DEFAULT_BASE_MASTER_SEED
            if args.base_master_seed is None
            else args.base_master_seed
        ),
        output_directory=(
            "artifacts/fatigue_recovery_sigma_factorial"
            if args.output_directory is None
            else str(args.output_directory)
        ),
        retain_details=(
            "compact" if args.retain_details is None else args.retain_details
        ),
    )


def _progress(payload: dict[str, Any]) -> None:
    print(canonical_json({"progress": payload}), flush=True)


def run_factorial_validation_cli(
    args: Any,
    *,
    repo_root: Path | None = None,
) -> int:
    if args.resume is not None:
        if args.plan_only:
            raise ValueError("--plan-only cannot be combined with --resume")
        conflicts = (
            args.validation_preset,
            args.base_master_seed,
            args.participants_per_type,
            args.maximum_sessions,
            args.output_directory,
            args.retain_details,
        )
        if any(value is not None for value in conflicts):
            raise ValueError("new-run factorial options cannot be combined with --resume")
        if not args.resume.is_dir():
            raise ValueError(f"resume directory does not exist: {args.resume}")
        runner = FatigueRecoverySigmaFactorialRunner(
            repo_root=repo_root,
            resume_directory=args.resume,
            progress_callback=_progress,
            allow_dirty_code=args.allow_dirty_factorial_code,
        )
    else:
        if args.conditions_json is not None or args.validation_config is not None:
            raise ValueError(
                "Stage 8A.3.1 uses the fixed A/B/C/D matrix; custom Stage 8A.3 "
                "condition/config files are not accepted"
            )
        if args.permutation_count is not None:
            raise ValueError("--permutation-count is a Stage 8A.3-only option")
        config = _config_from_args(args)
        if args.plan_only:
            print(
                json.dumps(
                    factorial_plan_projection(config),
                    allow_nan=False,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        runner = FatigueRecoverySigmaFactorialRunner(
            config,
            repo_root=repo_root,
            progress_callback=_progress,
            allow_dirty_code=args.allow_dirty_factorial_code,
        )
    previous_handlers: dict[signal.Signals, Any] = {}

    def handle_signal(signum: int, _frame: Any) -> None:
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

    for selected_signal in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[selected_signal] = signal.getsignal(selected_signal)
        signal.signal(selected_signal, handle_signal)
    try:
        summary = runner.run()
    finally:
        for selected_signal, handler in previous_handlers.items():
            signal.signal(selected_signal, handler)
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


__all__ = ["run_factorial_validation_cli"]
