"""Headless CLI adapter for Stage 8A.3 local validation."""

from __future__ import annotations

import json
import signal
from dataclasses import replace
from pathlib import Path
from typing import Any

from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.job import canonical_json

from .config import (
    DEFAULT_BASE_MASTER_SEED,
    ValidationConfig,
    load_conditions_json,
    validation_plan_projection,
)
from .runner import AdaptivePlaceboValidationRunner


def _config_from_args(args: Any) -> ValidationConfig:
    conditions = (
        None
        if args.conditions_json is None
        else load_conditions_json(args.conditions_json)
    )
    if args.validation_config is not None:
        if not args.validation_config.is_file():
            raise ValueError(
                f"validation config does not exist: {args.validation_config}"
            )
        config = ValidationConfig.from_json(
            args.validation_config.read_text(encoding="utf-8")
        )
        replacements: dict[str, Any] = {}
        if conditions is not None:
            replacements["conditions"] = conditions
        if args.output_directory is not None:
            replacements["output_directory"] = str(args.output_directory)
        if args.base_master_seed is not None:
            replacements["base_master_seed"] = args.base_master_seed
        if args.participants_per_type is not None:
            replacements["participants_per_type"] = args.participants_per_type
        if args.maximum_sessions is not None:
            replacements["maximum_sessions"] = args.maximum_sessions
        if args.permutation_count is not None:
            replacements["permutation_count"] = args.permutation_count
        if args.retain_details is not None:
            replacements["retain_details"] = args.retain_details
        return replace(config, **replacements)
    return ValidationConfig.create(
        validation_preset=args.validation_preset or "standard",
        conditions=conditions,
        participants_per_type=args.participants_per_type,
        maximum_sessions=args.maximum_sessions,
        permutation_count=args.permutation_count,
        base_master_seed=(
            DEFAULT_BASE_MASTER_SEED
            if args.base_master_seed is None
            else args.base_master_seed
        ),
        output_directory=(
            "artifacts/adaptive_placebo_validation"
            if args.output_directory is None
            else str(args.output_directory)
        ),
        retain_details=(
            "compact" if args.retain_details is None else args.retain_details
        ),
    )


def _progress(payload: dict[str, Any]) -> None:
    print(canonical_json({"progress": payload}), flush=True)


def run_validation_cli(args: Any, *, repo_root: Path | None = None) -> int:
    if args.resume is not None:
        if args.plan_only:
            raise ValueError("--plan-only cannot be combined with --resume")
        conflicts = (
            args.validation_preset,
            args.conditions_json,
            args.validation_config,
            args.base_master_seed,
            args.participants_per_type,
            args.maximum_sessions,
            args.permutation_count,
            args.output_directory,
            args.retain_details,
        )
        if any(value is not None for value in conflicts):
            raise ValueError("new-run validation options cannot be combined with --resume")
        if not args.resume.is_dir():
            raise ValueError(f"resume directory does not exist: {args.resume}")
        runner = AdaptivePlaceboValidationRunner(
            repo_root=repo_root,
            resume_directory=args.resume,
            progress_callback=_progress,
            allow_dirty_code=args.allow_dirty_adaptive_placebo_code,
        )
    else:
        config = _config_from_args(args)
        if args.plan_only:
            print(
                json.dumps(
                    validation_plan_projection(config),
                    allow_nan=False,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
        runner = AdaptivePlaceboValidationRunner(
            config,
            repo_root=repo_root,
            progress_callback=_progress,
            allow_dirty_code=args.allow_dirty_adaptive_placebo_code,
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


__all__ = ["run_validation_cli"]
