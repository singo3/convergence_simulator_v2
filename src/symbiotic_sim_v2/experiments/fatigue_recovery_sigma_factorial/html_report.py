"""Self-contained Stage 8A.3.1 HTML report and drill-down pages."""

# ruff: noqa: E501 -- literal offline HTML/CSS is kept readable as a template.

from __future__ import annotations

import html
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from symbiotic_sim_v2.experiments.adaptive_placebo_validation.config import (
    ValidationParticipant,
)
from symbiotic_sim_v2.experiments.adaptive_placebo_validation.records import (
    BundleOutcome,
    SessionOutcome,
)
from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.checkpoint import (
    atomic_write_text,
)

from .charts import (
    factor_plot_svg,
    overall_condition_grid,
    participant_factorial_grid,
    participant_paired_lines_svg,
    user_type_factorial_grid,
    user_type_heatmap_svg,
)
from .conditions import CONDITION_IDS, FactorialValidationCondition
from .config import FACTORIAL_REPORT_VERSION


def _escape(value: object) -> str:
    if value is None:
        return "—"
    return html.escape(str(value))


def _table(
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[str] | None = None,
) -> str:
    if not rows:
        return "<p class='muted'>No rows.</p>"
    selected_fields = tuple(fields or sorted({key for row in rows for key in row}))
    head = "".join(f"<th>{_escape(field)}</th>" for field in selected_fields)
    body = "".join(
        "<tr>"
        + "".join(f"<td>{_escape(row.get(field))}</td>" for field in selected_fields)
        + "</tr>"
        for row in rows
    )
    return f"<div class='table-wrap'><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>"


def _css() -> str:
    return """
:root{color-scheme:light;background:#f5f7f6;color:#17212b;font-family:Inter,-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif}
body{margin:0}.page{max-width:1440px;margin:auto;padding:24px}header{background:#17384d;color:#fff;padding:28px;border-radius:14px}section{background:#fff;margin:18px 0;padding:18px;border:1px solid #dbe2e4;border-radius:12px;box-shadow:0 3px 12px #2030400b}.meta,.muted{color:#677680}.notice{border-left:5px solid #bf6c52;background:#fff8ed;padding:12px}.good{border-left-color:#16885e}.factorial-participant-grid,.factorial-user-type-grid,.factorial-overall-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.factorial-condition-panel{margin:0;padding:10px;overflow:auto}.factorial-condition-panel svg{min-width:650px;width:100%;height:auto}.chart-row{display:flex;flex-wrap:wrap;gap:12px}.chart-row svg{max-width:100%;height:auto;background:#fff}.table-wrap{overflow:auto}table{border-collapse:collapse;width:100%;font-size:12px}th,td{border:1px solid #d9e0e3;padding:6px;text-align:left;vertical-align:top}th{background:#edf3f4;position:sticky;top:0}code{background:#edf2f3;padding:2px 5px;border-radius:4px}a{color:#176b92}@media(max-width:900px){.factorial-participant-grid,.factorial-user-type-grid,.factorial-overall-grid{grid-template-columns:1fr}.page{padding:10px}}
"""


def _page(title: str, body: str) -> str:
    return (
        "<!doctype html><html lang='ja'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{html.escape(title)}</title><style>{_css()}</style></head>"
        f"<body><main class='page'>{body}</main></body></html>"
    )


def _condition_conclusion(
    recommendation: Mapping[str, Any],
) -> str:
    decision_by_id = {
        str(item["condition_id"]): item for item in recommendation.get("condition_decisions", ())
    }
    items = "".join(
        f"<li><code>{html.escape(condition_id)}</code>: "
        f"{_escape(decision_by_id.get(condition_id, {}).get('recommendation'))}</li>"
        for condition_id in CONDITION_IDS
    )
    return (
        f"<p><strong>結論:</strong> {_escape(recommendation.get('overall_decision'))}; "
        f"preferred={_escape(recommendation.get('preferred_condition_id'))}; "
        f"明確な勝者={_escape(recommendation.get('clear_winner'))}</p><ul>{items}</ul>"
    )


def build_html_report(
    *,
    manifest: Mapping[str, Any],
    conditions: Sequence[FactorialValidationCondition],
    participants: Sequence[ValidationParticipant],
    bundles: Sequence[BundleOutcome],
    sessions: Sequence[SessionOutcome],
    analysis: Mapping[str, Sequence[Mapping[str, Any]]],
    condition_summaries: Sequence[Mapping[str, Any]],
    recommendation: Mapping[str, Any],
    reproduction_command: str,
) -> str:
    participant_rows = analysis.get("participant_condition_effects", ())
    condition_table = _table(
        [item.to_dict() for item in conditions],
        (
            "condition_id",
            "session_end_recovery_policy",
            "sigma_multiplier",
            "effective_selected_session_fatigue_target",
            "eta_selected",
            "rho",
            "formal_spec_adoption",
        ),
    )
    summary_table = _table(
        condition_summaries,
        (
            "condition_id",
            "nonflat_mean_effect_ms",
            "nonflat_effect_lower95_ms",
            "nonflat_effect_upper95_ms",
            "worst_user_type_effect_ms",
            "nonflat_positive_participant_count",
            "nonflat_positive_rate",
            "flat_control_arm_difference_ms",
            "selection_enrichment_advantage",
            "lagged_coupling_advantage",
            "w_ceiling_blocked_rate",
            "invalid_session_rate",
            "reject_rate",
        ),
    )
    factor_charts = "".join(
        factor_plot_svg(condition_summaries, metric=metric)
        for metric in (
            "nonflat_mean_effect_ms",
            "nonflat_positive_rate",
            "worst_user_type_effect_ms",
            "selection_enrichment_advantage",
            "holder_switch_rate",
        )
    )
    heatmaps = "".join(
        user_type_heatmap_svg(participant_rows, metric=metric)
        for metric in (
            "late_delta_rmssd_advantage_ms",
            "positive_participant_rate",
            "full_pattern_selection_enrichment_advantage",
            "lagged_pattern_advantage",
        )
    )
    body = f"""
<header><h1>Stage 8A.3.1 疲労回復方式 × 探索幅 2×2追加検証</h1><p>{FACTORIAL_REPORT_VERSION} · run {_escape(manifest.get("run_id"))}</p></header>
<section><h2>1. 検証目的</h2><p>実人間による自律確認MVPの条件候補を、simulation-onlyのparticipant-paired比較で検討する。主要比較はautonomous closed loop対shared pure random open loopである。</p></section>
<section><h2>2. 2×2 factor定義</h2><p>Factor 1は非選出生命のsession-end全回復なし/あり、Factor 2は探索幅倍率1.0/0.5。4条件のselected etaとsession内rhoは同一である。</p>{factor_charts}</section>
<section><h2>3. 4条件</h2>{condition_table}</section>
<section><h2>4. 実行計画</h2>{_table([manifest.get("plan", {})])}</section>
<section><h2>5. 全体結果</h2>{summary_table}{overall_condition_grid(sessions)}</section>
<section><h2>6. user type別結果</h2>{heatmaps}</section>
<section><h2>7. participant別結果</h2><p>{len(participants)} participants。各participantページに4条件×2 armsを同一BPM scaleで示す。</p>{participant_paired_lines_svg(participant_rows)}</section>
<section><h2>8. v2 referenceとの比較</h2>{_condition_conclusion(recommendation)}</section>
<section><h2>9. sigma 0.5の主効果</h2>{_table([row for row in analysis.get("factorial_overall_effects", ()) if row.get("outcome") == "late_delta_rmssd_advantage_ms"])}</section>
<section><h2>10. full recoveryの主効果</h2>{_table(analysis.get("factorial_overall_effects", ()))}</section>
<section><h2>11. interaction</h2><p><code>(D-C)-(B-A)=(D-B)-(C-A)</code>をparticipantごとに保存し、同一性誤差を監査する。</p>{_table(analysis.get("factorial_overall_effects", ()))}</section>
<section><h2>12. RMSSD利益</h2>{_table(analysis.get("benefits", ()), ("condition_id", "arm", "late_session_mean_delta_rmssd_ms", "late_minus_early_ms", "delta_rmssd_session_slope"))}</section>
<section><h2>13. lagged coupling</h2><p>同時点light−RMSSDとは分離し、過去sessionだけから将来選択とのcouplingを評価した。</p>{_table(analysis.get("lagged", ()))}</section>
<section><h2>14. selection enrichment</h2>{_table(analysis.get("participant_condition_effects", ()), ("participant_id", "condition_id", "life_selection_enrichment_advantage", "bpm_selection_enrichment_advantage", "full_pattern_selection_enrichment_advantage"))}</section>
<section><h2>15. participant positive rate</h2>{summary_table}</section>
<section><h2>16. flat control</h2><p>absolute arm differenceのgateは0.25 ms以下。好み由来と機械的holder switchを混同しない。</p>{summary_table}</section>
<section><h2>17. W ceiling</h2>{_table(participant_rows, ("participant_id", "condition_id", "w_ceiling_blocked_rate", "candidate_count", "provisional_success_count", "accepted_candidate_count"))}</section>
<section><h2>18. holder / Hue / BPM trajectory</h2><p>横軸=session index、縦軸=blink BPM、塗り=actual Hue、形=life ID。trialは半透明、代表点は大きい点。</p>{user_type_factorial_grid(analysis.get("user_type_trajectory", ()))}</section>
<section><h2>19. type-specific risk</h2>{_table(condition_summaries, ("condition_id", "type_specific_failures", "worst_user_type_id", "worst_user_type_effect_ms"))}</section>
<section><h2>20. 実人間MVP条件候補</h2>{_condition_conclusion(recommendation)}<p>不透明な総合scoreを使わず、全gateと弱点を保存した。条件を正式仕様へ自動採用しない。</p></section>
<section><h2>21. 不確実性</h2><p>95% participant bootstrap intervalを併記する。smokeは配線確認であり、条件選択の根拠にはしない。</p></section>
<section><h2>22. reproduction command</h2><pre>{html.escape(reproduction_command)}</pre></section>
<section class='notice'><h2>23. formal_spec_adoption=false</h2><p>v2.0 reference Coreは不変。B/C/Dは実験条件であり、結果をCore、探索、停止条件へ返さない。</p></section>
<section class='notice'><h2>24. simulation-only注意事項</h2><p>仮想参加者上の追加検証であり、実人間での有効性を主張しない。moving preference、context依存、yoked再設計は未実装。</p></section>
"""
    return _page("Stage 8A.3.1 factorial validation", body)


def write_html_reports(
    run_directory: Path,
    *,
    manifest: Mapping[str, Any],
    conditions: Sequence[FactorialValidationCondition],
    participants: Sequence[ValidationParticipant],
    bundles: Sequence[BundleOutcome],
    sessions: Sequence[SessionOutcome],
    analysis: Mapping[str, Sequence[Mapping[str, Any]]],
    condition_summaries: Sequence[Mapping[str, Any]],
    recommendation: Mapping[str, Any],
    reproduction_command: str,
) -> tuple[Path, tuple[Path, ...], tuple[Path, ...]]:
    report_directory = run_directory / "report"
    participant_directory = report_directory / "participants"
    user_type_directory = report_directory / "user_types"
    participant_directory.mkdir(parents=True, exist_ok=True)
    user_type_directory.mkdir(parents=True, exist_ok=True)
    main_path = report_directory / "report.html"
    atomic_write_text(
        main_path,
        build_html_report(
            manifest=manifest,
            conditions=conditions,
            participants=participants,
            bundles=bundles,
            sessions=sessions,
            analysis=analysis,
            condition_summaries=condition_summaries,
            recommendation=recommendation,
            reproduction_command=reproduction_command,
        ),
    )
    participant_effects = analysis.get("participant_condition_effects", ())
    participant_paths: list[Path] = []
    for participant in participants:
        rows = [
            row
            for row in participant_effects
            if row.get("participant_id") == participant.participant_id
        ]
        body = (
            "<header><p><a href='../report.html'>← 全体</a></p>"
            f"<h1>{html.escape(participant.participant_id)}</h1></header>"
            "<section><h2>4 conditions × 2 arms</h2>"
            + participant_factorial_grid(
                participant.participant_id,
                bundles,
                sessions,
            )
            + "</section><section><h2>participant effects</h2>"
            + _table(rows)
            + "</section>"
        )
        path = participant_directory / f"{participant.participant_id}.html"
        atomic_write_text(path, _page(participant.participant_id, body))
        participant_paths.append(path)
    user_type_paths: list[Path] = []
    for user_type_id in sorted({item.user_type_id for item in participants}):
        rows = [row for row in participant_effects if row.get("user_type_id") == user_type_id]
        body = (
            "<header><p><a href='../report.html'>← 全体</a></p>"
            f"<h1>{html.escape(user_type_id)}</h1></header>"
            "<section><h2>condition × arm trajectory</h2>"
            + user_type_factorial_grid(
                analysis.get("user_type_trajectory", ()),
                user_type_id=user_type_id,
            )
            + "</section><section><h2>participant effects</h2>"
            + _table(rows)
            + "</section>"
        )
        path = user_type_directory / f"{user_type_id}.html"
        atomic_write_text(path, _page(user_type_id, body))
        user_type_paths.append(path)
    return main_path, tuple(participant_paths), tuple(user_type_paths)


__all__ = ["build_html_report", "write_html_reports"]
