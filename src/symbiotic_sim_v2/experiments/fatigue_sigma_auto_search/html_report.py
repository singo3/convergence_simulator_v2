"""Self-contained, offline Stage 8A.2 HTML report."""

# ruff: noqa: E501 -- literal offline HTML/CSS is kept readable as a template.

from __future__ import annotations

import html
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .checkpoint import atomic_write_text
from .config import HTML_REPORT_VERSION


def _escape(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return html.escape(f"{value:.4f}")
    return html.escape(str(value))


def _candidate_table(
    summaries: Sequence[Mapping[str, Any]],
    pareto_by_id: Mapping[str, Mapping[str, Any]],
) -> str:
    rows = []
    for item in summaries:
        pareto = pareto_by_id.get(str(item["candidate_id"]), {})
        rows.append(
            "<tr>"
            f"<td>{_escape(item['candidate_id'])}</td>"
            f"<td>{_escape(item['selected_session_fatigue_target'])}</td>"
            f"<td>{_escape(item['sigma_multiplier'])}</td>"
            f"<td>{_escape(item.get('worst_nonflat_correct_structure_lower95'))}</td>"
            f"<td>{_escape(item.get('flat_spurious_structure_upper95'))}</td>"
            f"<td>{_escape(item.get('flat_rotation_upper95'))}</td>"
            f"<td>{_escape(item.get('W_ceiling_blocked_upper95'))}</td>"
            f"<td>{_escape(pareto.get('pareto_rank'))}</td>"
            f"<td>{_escape(pareto.get('gate_pass'))}</td>"
            "</tr>"
        )
    return "".join(rows) or "<tr><td colspan='9'>No completed candidates</td></tr>"


def _heatmap(summaries: Sequence[Mapping[str, Any]]) -> str:
    if not summaries:
        return "<p>No heatmap data.</p>"
    fatigue = sorted({float(item["selected_session_fatigue_target"]) for item in summaries})
    sigma = sorted({float(item["sigma_multiplier"]) for item in summaries})
    lookup = {
        (
            float(item["selected_session_fatigue_target"]),
            float(item["sigma_multiplier"]),
        ): item.get("mean_nonflat_correct_structure_rate")
        for item in summaries
    }
    cell = 46
    left = 80
    top = 28
    width = left + cell * len(sigma) + 10
    height = top + cell * len(fatigue) + 38
    parts = [
        f"<svg viewBox='0 0 {width} {height}' role='img' aria-label='fatigue by sigma heatmap'>"
    ]
    for column, value in enumerate(sigma):
        parts.append(
            f"<text x='{left + column * cell + cell / 2}' y='18' "
            f"text-anchor='middle'>{_escape(value)}</text>"
        )
    for row, fatigue_value in enumerate(fatigue):
        y = top + row * cell
        parts.append(
            f"<text x='{left - 8}' y='{y + 28}' text-anchor='end'>{_escape(fatigue_value)}</text>"
        )
        for column, sigma_value in enumerate(sigma):
            value = lookup.get((fatigue_value, sigma_value))
            intensity = 0 if value is None else max(0, min(255, round(float(value) * 190)))
            color = f"rgb({235 - intensity // 2},{244 - intensity // 3},{245 - intensity})"
            label = "—" if value is None else f"{float(value):.2f}"
            x = left + column * cell
            parts.append(
                f"<rect x='{x}' y='{y}' width='{cell - 2}' height='{cell - 2}' "
                f"fill='{color}' rx='4'/><text x='{x + cell / 2}' y='{y + 28}' "
                f"text-anchor='middle'>{html.escape(label)}</text>"
            )
    parts.append("</svg>")
    return "".join(parts)


def _user_type_rows(summaries: Sequence[Mapping[str, Any]]) -> str:
    rows = []
    for summary in summaries:
        for user_type_id, values in summary.get("user_type_breakdown", {}).items():
            correct = values.get("correct_structure", {})
            diffuse = values.get("diffuse", {})
            rows.append(
                "<tr>"
                f"<td>{_escape(summary['candidate_id'])}</td>"
                f"<td>{_escape(user_type_id)}</td>"
                f"<td>{_escape(values.get('completed_replicate_count'))}</td>"
                f"<td>{_escape(correct.get('rate'))}</td>"
                f"<td>{_escape(correct.get('lower95'))}</td>"
                f"<td>{_escape(correct.get('upper95'))}</td>"
                f"<td>{_escape(diffuse.get('rate'))}</td>"
                "</tr>"
            )
    return "".join(rows) or "<tr><td colspan='7'>No user-type data.</td></tr>"


def _diagnostic_rows(
    summaries: Sequence[Mapping[str, Any]],
    fields: Sequence[tuple[str, str]],
) -> str:
    rows = []
    for summary in summaries:
        cells = "".join(f"<td>{_escape(summary.get(field))}</td>" for field, _ in fields)
        rows.append(f"<tr><td>{_escape(summary['candidate_id'])}</td>{cells}</tr>")
    return "".join(rows) or (
        f"<tr><td colspan='{len(fields) + 1}'>No completed candidates.</td></tr>"
    )


def _diagnostic_table(
    summaries: Sequence[Mapping[str, Any]],
    fields: Sequence[tuple[str, str]],
) -> str:
    headings = "".join(f"<th>{_escape(label)}</th>" for _, label in fields)
    return (
        "<table><thead><tr><th>candidate</th>"
        f"{headings}</tr></thead><tbody>{_diagnostic_rows(summaries, fields)}</tbody></table>"
    )


def _reference_table(reference_results: Sequence[Mapping[str, Any]]) -> str:
    rows = []
    for item in reference_results:
        rows.append(
            "<tr>"
            f"<td>{_escape(item.get('user_type_id'))}</td>"
            f"<td>{_escape(item.get('maximum_sessions'))}</td>"
            f"<td>{_escape(item.get('replicate_index'))}</td>"
            f"<td>{_escape(item.get('replicate_master_seed'))}</td>"
            f"<td><code>{_escape(json.dumps(item.get('latest_structured_convergence'), ensure_ascii=False, sort_keys=True))}</code></td>"
            f"<td><code>{_escape(json.dumps(item.get('latest_truth_alignment'), ensure_ascii=False, sort_keys=True))}</code></td>"
            "</tr>"
        )
    return "".join(rows) or "<tr><td colspan='6'>Reference arm was not requested.</td></tr>"


def build_html_report(
    *,
    manifest: Mapping[str, Any],
    runtime_summary: Mapping[str, Any],
    summaries: tuple[Mapping[str, Any], ...],
    pareto_records: tuple[Mapping[str, Any], ...],
    recommendations: Mapping[str, Any],
    phase_selection_history: Sequence[Mapping[str, Any]],
    reproduction_commands: tuple[str, ...],
    reference_results: Sequence[Mapping[str, Any]] = (),
) -> str:
    pareto_by_id = {str(item["candidate_id"]): item for item in pareto_records}
    status = str(recommendations.get("status", "incomplete"))
    smoke_notice = (
        "<p class='notice'>Smoke is an implementation check only; it does not "
        "establish an optimal or robust condition.</p>"
        if manifest.get("config", {}).get("search_preset") == "smoke"
        else ""
    )
    blockers = recommendations.get("no_candidate_blockers", {})
    blocker_html = (
        "<ul>"
        + "".join(f"<li>{_escape(name)}: {_escape(count)}</li>" for name, count in blockers.items())
        + "</ul>"
        if blockers
        else "<p>None.</p>"
    )
    specialist_html = "".join(
        "<li>"
        f"{_escape(category)}: "
        f"{_escape(None if candidate is None else candidate.get('candidate_id'))}"
        "</li>"
        for category, candidate in recommendations.get("specialist_candidates", {}).items()
    )
    phase_html = (
        "".join(
            f"<li><code>{_escape(json.dumps(item, ensure_ascii=False, sort_keys=True))}</code></li>"
            for item in phase_selection_history
        )
        or "<li>No phase transition in this run.</li>"
    )
    commands = "".join(
        f"<pre><code>{_escape(command)}</code></pre>" for command in reproduction_commands
    )
    fingerprint = manifest.get("code_fingerprint", {})
    flat_table = _diagnostic_table(
        summaries,
        (
            ("flat_spurious_structure_rate", "spurious rate"),
            ("flat_spurious_structure_upper95", "spurious upper95"),
            ("flat_holder_switch_rate", "holder switch"),
        ),
    )
    rotation_table = _diagnostic_table(
        summaries,
        (
            ("flat_mechanical_rotation_warning_rate", "rotation rate"),
            ("flat_rotation_upper95", "rotation upper95"),
        ),
    )
    w_ceiling_table = _diagnostic_table(
        summaries,
        (
            ("W_ceiling_blocked_rate", "blocked rate"),
            ("W_ceiling_blocked_upper95", "blocked upper95"),
            ("accepted_candidate_count", "formal adoptions observed"),
            ("provisional_success_count", "provisional successes"),
        ),
    )
    convergence_table = _diagnostic_table(
        summaries,
        (
            ("valid_session_rate", "valid sessions"),
            ("median_first_structure_session", "median first structure session"),
            ("convergence_rate", "any structure rate"),
        ),
    )
    outlier_table = _diagnostic_table(
        summaries,
        (
            ("post_convergence_outlier_rate", "post-convergence outlier rate"),
            ("return_within_2_rate", "return within 2 rate"),
        ),
    )
    small_samples = [
        str(item["candidate_id"])
        for item in summaries
        if item.get("uncertainty", {}).get("small_sample_warning")
    ]
    return f"""<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Stage 8A.2 Automatic Condition Search</title>
<style>
:root{{--ink:#18202a;--muted:#5b6878;--paper:#fff;--line:#dce3ea;--accent:#176b68;}}
*{{box-sizing:border-box}} body{{margin:0;background:#f4f7f8;color:var(--ink);font:14px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:30px}} section{{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:20px;margin:14px 0}}
h1,h2{{margin:.1em 0 .6em}} h1{{font-size:28px}} h2{{font-size:19px}} .meta{{color:var(--muted)}} .notice{{border-left:4px solid #d88916;background:#fff6df;padding:10px}}
.status{{display:inline-block;background:#e5f3f1;color:#0b5855;border-radius:999px;padding:5px 10px;font-weight:700}} table{{border-collapse:collapse;width:100%;font-size:12px}}
th,td{{border:1px solid var(--line);padding:7px;text-align:left;vertical-align:top}} th{{background:#edf4f4}} pre{{white-space:pre-wrap;background:#17202a;color:#eef6f7;padding:12px;border-radius:8px;overflow:auto}} svg{{max-width:100%;height:auto}} code{{word-break:break-word}}
</style>
</head>
<body><main>
<header><h1>Stage 8A.2 自動条件探索レポート</h1><p class="meta">{_escape(HTML_REPORT_VERSION)}</p><span class="status">{_escape(status)}</span></header>
{smoke_notice}
<section><h2>1. 実験概要</h2><p>Stage 8A.1 runnerを再利用したローカルCPU専用の条件探索です。report path: <code>{_escape(runtime_summary.get("report_path"))}</code></p></section>
<section><h2>2. Code / spec fingerprint</h2><pre>{_escape(json.dumps(fingerprint, ensure_ascii=False, indent=2, sort_keys=True))}</pre></section>
<section><h2>3. Search presetとphase</h2><p>preset: {_escape(manifest.get("config", {}).get("search_preset"))} / final phase: {_escape(runtime_summary.get("final_phase"))}</p></section>
<section><h2>4. Runtime・完了job・失敗job</h2><p>completed jobs: {_escape(runtime_summary.get("completed_jobs"))} / failed jobs: {_escape(runtime_summary.get("failed_jobs"))} / completed sessions: {_escape(runtime_summary.get("completed_session_runs"))} / planned sessions: {_escape(runtime_summary.get("planned_session_runs"))} / runtime: {_escape(runtime_summary.get("elapsed_seconds"))} s</p></section>
<section><h2>5. 推奨候補</h2><p>robust候補はbalanced gate通過後に不確実性を含む辞書順rankingで残った条件です。単一の不透明scoreは使用していません。</p><pre>{_escape(json.dumps(recommendations.get("robust_candidate"), ensure_ascii=False, indent=2, sort_keys=True))}</pre><ul>{specialist_html}</ul></section>
<section><h2>6. Robust候補なしの場合のblocker</h2>{blocker_html}</section>
<section><h2>7. Pareto frontier</h2><table><thead><tr><th>candidate</th><th>fatigue</th><th>sigma</th><th>worst lower95</th><th>flat upper95</th><th>rotation upper95</th><th>W ceiling upper95</th><th>rank</th><th>gate</th></tr></thead><tbody>{_candidate_table(summaries, pareto_by_id)}</tbody></table></section>
<section><h2>8. 疲労 × sigma heatmap</h2>{_heatmap(summaries)}</section>
<section><h2>9. User type別correct structure</h2><p>lower95が最も低い非flat user typeが各候補の観測上の弱点です。</p><table><thead><tr><th>candidate</th><th>user type</th><th>completed replicates</th><th>correct rate</th><th>lower95</th><th>upper95</th><th>diffuse rate</th></tr></thead><tbody>{_user_type_rows(summaries)}</tbody></table></section>
<section><h2>10. Flat control安全診断</h2><p>好み構造がないcontrolでの偽構造とholder switchです。upper95をgateと併せて確認します。</p>{flat_table}</section>
<section><h2>11. Mechanical rotation</h2><p>疲労に駆動された機械的rotationを好み由来の構造と分離します。</p>{rotation_table}</section>
<section><h2>12. W ceiling</h2><p>blocked upper95が高い候補は、探索がW ceilingで止まり評価不能になっていないか追加確認が必要です。formal adoptions observedはDigital Life自身の既存採用規則による件数であり、Stage 8A.2による採用ではありません。</p>{w_ceiling_table}</section>
<section><h2>13. Convergence速度</h2>{convergence_table}</section>
<section><h2>14. Outlierと復帰</h2>{outlier_table}</section>
<section><h2>15. Reference arm差</h2><p>{_escape(runtime_summary.get("reference_cache_entries"))} cached reference entries. Referenceはcondition横断で再利用され、詳細比較は<code>results/reference_arm_comparison.csv</code>にも保存されます。</p><table><thead><tr><th>user type</th><th>sessions</th><th>replicate</th><th>paired seed</th><th>latest structure</th><th>latest truth alignment</th></tr></thead><tbody>{_reference_table(reference_results)}</tbody></table></section>
<section><h2>16. Phase 1 → 2 → 3 絞り込み</h2><ul>{phase_html}</ul></section>
<section><h2>17. 不確実性</h2><p>割合は95% Wilson interval、連続値はcount/mean/median/min/max/Q1/Q3です。少数replicateでは不確実性が大きく、統計的有意差や人での有効性は主張しません。</p><p>small-sample candidates: {_escape(", ".join(small_samples) if small_samples else "none")}</p></section>
<section><h2>18. 再現コマンド</h2>{commands}</section>
<section><h2>19. Formal scope</h2><p><strong>formal_spec_adoption=false</strong></p><p>Stage 8A.2は観測・実験オーケストレーションです。Digital Life Core、Runtime、Garden、v2.0 reference Profileへ推薦を返しません。</p></section>
<section><h2>20. 注意事項と次の検証</h2><p>trade-off、弱いuser type、flat control、W ceiling、replicate数を確認し、必要ならstandard後にrobustをローカルCPUで実行してください。結果は正式Profileへ自動採用されません。</p></section>
</main></body></html>"""


def write_html_report(path: Path, **values: Any) -> Path:
    document = build_html_report(**values)
    lowered = document.lower()
    if any(token in lowered for token in ("http://", "https://", 'src="//', "src='//")):
        raise ValueError("HTML report must not contain external URLs")
    atomic_write_text(path, document)
    return path


__all__ = ["build_html_report", "write_html_report"]
