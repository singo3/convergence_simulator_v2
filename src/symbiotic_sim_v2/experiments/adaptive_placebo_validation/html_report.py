"""Self-contained offline Stage 8A.3 HTML and participant reports."""

# ruff: noqa: E501 -- keeping the literal offline HTML template readable is useful.

from __future__ import annotations

import html
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from symbiotic_sim_v2.experiments.fatigue_sigma_auto_search.checkpoint import (
    atomic_write_text,
)

from .charts import (
    correlation_scatter_svg,
    overall_adaptation_metrics_svg,
    overall_classification_bars,
    overall_delta_svg,
    participant_trajectory_svg,
    user_type_average_svg,
)
from .config import VALIDATION_REPORT_VERSION, ValidationCondition
from .records import BundleOutcome, SessionOutcome


def _escape(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        return html.escape(f"{value:.5f}")
    return html.escape(str(value))


def _table(
    rows: Sequence[Mapping[str, Any]],
    fields: Sequence[tuple[str, str]],
    *,
    limit: int | None = None,
) -> str:
    selected = rows if limit is None else rows[:limit]
    headings = "".join(f"<th>{html.escape(label)}</th>" for _key, label in fields)
    body = "".join(
        "<tr>"
        + "".join(f"<td>{_escape(row.get(key))}</td>" for key, _label in fields)
        + "</tr>"
        for row in selected
    )
    if not body:
        body = f"<tr><td colspan='{len(fields)}'>データなし</td></tr>"
    return f"<div class='table-wrap'><table><thead><tr>{headings}</tr></thead><tbody>{body}</tbody></table></div>"


def _css() -> str:
    return """
:root{--ink:#17232c;--muted:#5f6e79;--paper:#fff;--line:#dce4e8;--accent:#166b64;--warn:#8b5a2b}
*{box-sizing:border-box}body{margin:0;background:#f3f6f7;color:var(--ink);font:14px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
main{max-width:1220px;margin:auto;padding:28px}header,section{background:var(--paper);border:1px solid var(--line);border-radius:12px;padding:20px;margin:14px 0}
h1,h2,h3{margin:.1em 0 .65em}h1{font-size:27px}h2{font-size:19px}h3{font-size:15px}.meta,.subtle{color:var(--muted)}
.notice{border-left:4px solid #cf8419;background:#fff7e8;padding:10px}.good{border-left-color:var(--accent);background:#edf8f5}.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:12px}
table{border-collapse:collapse;width:100%;font-size:11px}th,td{border:1px solid var(--line);padding:6px;text-align:left;vertical-align:top}th{background:#edf3f4}.table-wrap{overflow:auto;max-height:470px}
svg{max-width:100%;height:auto;background:#fff}code{word-break:break-word}pre{white-space:pre-wrap;background:#15212a;color:#eef5f7;padding:12px;border-radius:8px;overflow:auto}
a{color:#075f77}.pill{display:inline-block;border-radius:999px;padding:4px 9px;background:#e7f2f1;margin:2px}.trajectory{border:1px solid var(--line);border-radius:8px}
details{border:1px solid var(--line);border-radius:8px;margin:8px 0;padding:8px}summary{cursor:pointer;font-weight:700}
"""


def _page(title: str, body: str) -> str:
    return f"""<!doctype html><html lang='ja'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{html.escape(title)}</title><style>{_css()}</style></head><body><main>{body}</main></body></html>"""


def _participant_page(
    participant_id: str,
    conditions: Sequence[ValidationCondition],
    bundles: Sequence[BundleOutcome],
    sessions: Sequence[SessionOutcome],
    paired: Sequence[Mapping[str, Any]],
    effects: Sequence[Mapping[str, Any]],
) -> str:
    participant_sessions = [item for item in sessions if item.participant_id == participant_id]
    participant_bundles = [item for item in bundles if item.participant_id == participant_id]
    paired_rows = [item for item in paired if item.get("participant_id") == participant_id]
    effect_rows = [item for item in effects if item.get("participant_id") == participant_id]
    charts = "".join(
        f"<h2>{html.escape(condition.condition_id)}</h2>"
        + participant_trajectory_svg(
            participant_id,
            condition.condition_id,
            participant_bundles,
            participant_sessions,
        )
        for condition in conditions
    )
    body = f"""
<header><p><a href='../report.html'>← 全体レポート</a></p><h1>{html.escape(participant_id)}</h1><p class='meta'>Stage 8A.3 participant-level diagnostic; classification is secondary.</p></header>
<section><h2>3 arm trajectory</h2><p>横軸=session、縦軸=blink BPM、塗り=actual Hue、形=life ID。小点はBundle実提示です。autonomousの大点はfinal committed anchorで、offsetされた小さいBundle 2 actualとは区別します。yoked/randomの大点はBundle 2 actual代表出力です。</p>{charts}</section>
<section><h2>Paired continuous effects</h2>{_table(paired_rows, (("condition_id","condition"),("comparator_arm","comparator"),("late_delta_rmssd_advantage_ms","late ΔRMSSD advantage"),("learning_gain_advantage_ms","learning gain advantage"),("slope_advantage","slope advantage"),("selection_enrichment_advantage","selection enrichment advantage")))}</section>
<section><h2>Secondary classification</h2>{_table(effect_rows, (("condition_id","condition"),("classification","classification"),("autonomous_minus_yoked_late_delta_rmssd_ms","late advantage"),("effect_interval_lower95","lower95"),("effect_interval_upper95","upper95"),("valid_session_count","valid sessions")))}</section>
<section><h2>Session outcomes</h2>{_table(tuple(item.to_dict() for item in participant_sessions), (("condition_id","condition"),("arm","arm"),("session_index","session"),("baseline_rmssd_ms","baseline RMSSD"),("mean_valid_bundle_delta_rmssd_ms","mean ΔRMSSD"),("representative_life_id","life"),("representative_hue_degree","Hue"),("representative_blink_bpm","BPM"),("session_valid","valid")))}</section>
"""
    return _page(f"Stage 8A.3 · {participant_id}", body)


def _lag_scatter_rows(sessions: Sequence[SessionOutcome]) -> tuple[dict[str, Any], ...]:
    grouped: dict[tuple[str, str, str], list[SessionOutcome]] = {}
    for row in sessions:
        grouped.setdefault((row.participant_id, row.condition_id, row.arm), []).append(row)
    result: list[dict[str, Any]] = []
    for rows in grouped.values():
        ordered = sorted(rows, key=lambda item: item.session_index)
        for current, future in zip(ordered[:-1], ordered[1:], strict=True):
            if current.mean_valid_bundle_delta_rmssd_ms is None:
                continue
            same_life = float(current.representative_life_id == future.representative_life_id)
            closeness: float | None = None
            if (
                current.representative_life_id == future.representative_life_id
                and current.representative_hue_degree is not None
                and future.representative_hue_degree is not None
                and current.representative_blink_bpm is not None
                and future.representative_blink_bpm is not None
            ):
                direct = abs(current.representative_hue_degree - future.representative_hue_degree) % 360.0
                hue_distance = min(direct, 360.0 - direct)
                normalized = hue_distance / 5.0 + abs(current.representative_blink_bpm - future.representative_blink_bpm) / 15.0
                closeness = 1.0 / (1.0 + normalized)
            result.append(
                {
                    "participant_id": current.participant_id,
                    "user_type_id": current.user_type_id,
                    "condition_id": current.condition_id,
                    "arm": current.arm,
                    "past_response": current.mean_valid_bundle_delta_rmssd_ms,
                    "next_same_life": same_life,
                    "next_pattern_closeness": closeness,
                }
            )
    return tuple(result)


def build_html_report(
    *,
    manifest: Mapping[str, Any],
    conditions: Sequence[ValidationCondition],
    participants: Sequence[Mapping[str, Any]],
    yoke_rows: Sequence[Mapping[str, Any]],
    bundles: Sequence[BundleOutcome],
    sessions: Sequence[SessionOutcome],
    analysis: Mapping[str, Sequence[Mapping[str, Any]]],
    baseline_diagnostics: Sequence[Mapping[str, Any]],
    reproduction_command: str,
    participant_links: Sequence[tuple[str, str]],
) -> str:
    paired = analysis.get("paired", ())
    contemporaneous = analysis.get("contemporaneous", ())
    effects = analysis.get("participant_effects", ())
    prospective = analysis.get("prospective", ())
    lagged = analysis.get("lagged", ())
    prediction = analysis.get("prediction", ())
    permutations = analysis.get("permutation", ())
    user_summary = analysis.get("user_type_summary", ())
    overall = analysis.get("overall_summary", ())
    trajectory = analysis.get("user_type_trajectory", ())
    invalid_sessions = [item for item in sessions if not item.session_valid]
    rejected_bundles = [item for item in bundles if not item.valid_for_analysis]
    participant_html = "".join(
        f"<li><a href='participants/{html.escape(filename)}'>{html.escape(participant_id)}</a></li>"
        for participant_id, filename in participant_links
    )
    condition_cards = "".join(
        f"<span class='pill'>{html.escape(item.condition_id)} · fatigue={item.selected_session_fatigue_target:g} · sigma×{item.sigma_multiplier:g} · formal adoption=false</span>"
        for item in conditions
    )
    overall_charts = "".join(
        f"<h3>{html.escape(condition.condition_id)}</h3>"
        f"{overall_delta_svg(sessions, condition.condition_id)}"
        f"{overall_adaptation_metrics_svg(prospective, sessions, condition.condition_id)}"
        f"{overall_classification_bars(tuple(item for item in effects if item.get('condition_id') == condition.condition_id))}"
        for condition in conditions
    )
    average_charts = "".join(
        f"<h3>{html.escape(condition.condition_id)}</h3>{user_type_average_svg(trajectory, condition.condition_id)}"
        for condition in conditions
    )
    lag_scatter = _lag_scatter_rows(sessions)
    scatter_html = "".join(
        f"<h3>{html.escape(condition.condition_id)}</h3><div class='grid2'>"
        + correlation_scatter_svg(tuple(item for item in lag_scatter if item.get("condition_id") == condition.condition_id), x_field="past_response", y_field="next_same_life", title="A. past response vs next same-life indicator")
        + correlation_scatter_svg(tuple(item for item in lag_scatter if item.get("condition_id") == condition.condition_id), x_field="past_response", y_field="next_pattern_closeness", title="B. past response vs next pattern closeness")
        + correlation_scatter_svg(tuple(item for item in prospective if item.get("condition_id") == condition.condition_id), x_field="actual_predicted_delta_rmssd_full_pattern", y_field="observed_future_delta_rmssd_ms", title="C. predicted vs observed future ΔRMSSD")
        + correlation_scatter_svg(tuple(item for item in prospective if item.get("condition_id") == condition.condition_id), x_field="full_pattern_selection_percentile", y_field="observed_future_delta_rmssd_ms", title="D. selection percentile vs observed future ΔRMSSD")
        + "</div>"
        for condition in conditions
    )
    smoke_notice = (
        "<p class='notice'>このsmokeは実装確認のみで、条件の有効性・最適性・人間での効果を示しません。</p>"
        if manifest.get("config", {}).get("validation_preset") == "smoke"
        else ""
    )
    body = f"""
<header><h1>Stage 8A.3 自律・反応切離しプラセボ・ランダム RMSSD個人内適応検証</h1><p class='meta'>{html.escape(VALIDATION_REPORT_VERSION)} · run {html.escape(str(manifest.get('run_id')))}</p>{smoke_notice}</header>
<section><h2>1. 検証仮説</h2><p>主要評価は、過去の本人ΔRMSSD反応が将来のlife/Hue/BPM選択へ結びつき、その選択が後のΔRMSSD利益を生むという時間方向付き関係です。全参加者がpositiveであることは要求せず、no_clear_effectを正当な結果として保持します。</p></section>
<section><h2>2. arm定義</h2><ul><li><b>autonomous_closed_loop</b>: target本人のRMSSDをq/k/資格競争を介して将来出力へ使う唯一のarm。</li><li><b>response_decoupled_yoked_replay</b>: 同じtypeの別participantによるautonomous formal light系列を正確に再生し、target RMSSDは出力へ使わない。</li><li><b>pure_random_open_loop</b>: RMSSD非依存の決定論的random holder/Hue/BPMを提示する。</li></ul></section>
<section><h2>3. condition</h2>{condition_cards}<p>provisional_f15_sigma050は暫定比較条件であり、v2.0への正式採用値ではありません。Stage 8A.3自身は条件を最適化しません。</p></section>
<section><h2>4. 仮想参加者cohort</h2><p>{len(participants)} target participants。好みとresponse strengthはrun中固定され、3armで共通です。</p>{_table(participants, (("participant_id","participant"),("user_type_id","user type"),("response_strength_scale","response scale"),("physiology_seed","physiology master seed"),("profile_hash","profile hash")))}</section>
<section><h2>5. contemporaneousとlaggedの違い</h2><p>同じBundleの光とΔRMSSDの同時点相関はyoked/randomでも生じ得ます。これは本人の反応が将来出力へ使われた証拠ではありません。BPM相関、Hue円環–線形相関、life別平均をlagged指標と別recordに保存します。</p>{_table(contemporaneous, (("participant_id","participant"),("condition_id","condition"),("arm","arm"),("valid_bundle_count","bundles"),("same_bundle_bpm_delta_rmssd_spearman","BPM Spearman"),("same_bundle_hue_delta_rmssd_circular_linear","Hue circular-linear"),("life_red_mean_delta_rmssd_ms","red mean"),("life_green_mean_delta_rmssd_ms","green mean"),("life_blue_mean_delta_rmssd_ms","blue mean")), limit=500)}</section>
<section><h2>6. 全体主要結果</h2>{_table(overall, (("condition_id","condition"),("participant_count","participants"),("valid_participant_count","valid"),("mean_autonomous_minus_yoked_late_delta_rmssd_ms","mean auto−yoked late ΔRMSSD"),("mean_autonomous_minus_random_late_delta_rmssd_advantage_ms","mean auto−random late ΔRMSSD"),("mean_autonomous_minus_yoked_selection_enrichment_advantage","selection enrichment advantage"),("mean_autonomous_minus_yoked_lagged_same_life_advantage","lagged same-life advantage"),("mean_autonomous_minus_yoked_slope_advantage","slope advantage"),("lower95","lower95"),("upper95","upper95")))}</section>
<section><h2>7. autonomous vs yoked</h2>{_table(tuple(item for item in paired if item.get("comparator_arm")=="response_decoupled_yoked_replay"), (("participant_id","participant"),("condition_id","condition"),("late_delta_rmssd_advantage_ms","late advantage"),("selection_enrichment_advantage","selection enrichment"),("lagged_same_life_advantage","same-life lag"),("slope_advantage","slope")))}</section>
<section><h2>8. autonomous vs random</h2>{_table(tuple(item for item in paired if item.get("comparator_arm")=="pure_random_open_loop"), (("participant_id","participant"),("condition_id","condition"),("late_delta_rmssd_advantage_ms","late advantage"),("selection_enrichment_advantage","selection enrichment"),("lagged_same_life_advantage","same-life lag"),("slope_advantage","slope")))}</section>
<section><h2>9. user type別結果</h2>{_table(user_summary, (("condition_id","condition"),("user_type_id","user type"),("participant_count","n"),("mean_autonomous_minus_yoked_late_delta_rmssd_ms","mean auto−yoked"),("mean_autonomous_minus_random_late_delta_rmssd_ms","mean auto−random"),("mean_autonomous_minus_yoked_selection_enrichment_advantage","selection enrichment advantage"),("mean_autonomous_minus_yoked_lagged_same_life_advantage","lagged same-life advantage"),("mean_autonomous_minus_yoked_slope_advantage","slope advantage"),("lower95","lower95"),("upper95","upper95"),("clear_positive_adaptation_rate","positive rate"),("no_clear_effect_rate","no-clear rate")))}</section>
<section><h2>10. participant別結果</h2><ul>{participant_html}</ul>{_table(effects, (("participant_id","participant"),("condition_id","condition"),("autonomous_minus_yoked_late_delta_rmssd_ms","continuous effect"),("effect_interval_lower95","lower95"),("effect_interval_upper95","upper95"),("classification","secondary classification")))}</section>
<section><h2>11. participant別BPM/Hue trajectory</h2><p>個別ページに同一BPM scaleの3panelを保存しました。Bundle offset、trial opacity、accepted/rejected outline、invalid ×を含みます。</p><ul>{participant_html}</ul></section>
<section><h2>12. user type平均trajectory</h2><p>BPM median/Q1/Q3、modal-life shape/share、modal-life circular Hueをparticipant単位で集計。Hue concentrationが低い点はhollow/低opacityです。下線はlife選択比率stackです。</p>{average_charts}</section>
<section><h2>13. ΔRMSSD session曲線・全participant平均グラフ</h2><p>participantを集計単位とし、session別mean ΔRMSSDと95% participant bootstrap interval、selection percentile、prospective enrichment、late windowの累積autonomous優位、responder classification割合をcondition別に表示します。</p>{overall_charts}</section>
<section><h2>14. lagged coupling</h2>{_table(lagged, (("participant_id","participant"),("condition_id","condition"),("arm","arm"),("lag_pair_count","pairs"),("lag1_response_vs_same_life","response→same life"),("lag1_response_vs_pattern_closeness","response→closeness"),("response_vs_revisit_within_2","revisit within2")))}</section>
<section><h2>15. prospective enrichment</h2>{_table(prospective, (("participant_id","participant"),("condition_id","condition"),("arm","arm"),("session_index","session"),("history_cutoff_session_index","history through"),("actual_predicted_delta_rmssd_full_pattern","actual predicted ΔRMSSD"),("full_pattern_counterfactual_mean_predicted_delta_rmssd_ms","counterfactual mean"),("full_pattern_counterfactual_median_predicted_delta_rmssd_ms","counterfactual median"),("full_pattern_selection_percentile","selection percentile"),("full_pattern_selection_enrichment","enrichment"),("observed_future_delta_rmssd_ms","observed ΔRMSSD")), limit=500)}</section>
<section><h2>16. prediction correlation</h2><p>予測相関はrandomでも固定反応地形を学習すれば正になり得るため、自律効果の単独根拠にはしません。</p>{_table(prediction, (("participant_id","participant"),("condition_id","condition"),("arm","arm"),("valid_prediction_count","n"),("pearson_correlation","Pearson"),("spearman_correlation","Spearman"),("mae","MAE"),("signed_bias","bias")))}</section>
<section><h2>17. permutation null</h2><p>participant内session-level ΔRMSSD labelのみを決定論的shuffleしたsimulation diagnosticです。臨床的有意差ではありません。</p>{_table(permutations, (("participant_id","participant"),("condition_id","condition"),("arm","arm"),("observed_statistic","observed"),("null_mean","null mean"),("null_standard_deviation","null SD"),("empirical_percentile","percentile"),("two_sided_empirical_p_like","p-like")))}</section>
<section><h2>18. participant effect classification</h2><p>連続effectを主要結果とし、分類は暫定simulation assumptionによる補助診断です。</p>{overall_classification_bars(effects)}{_table(effects, (("participant_id","participant"),("condition_id","condition"),("classification","classification"),("classification_is_primary","primary?")))}</section>
<section><h2>19. flat control</h2>{_table(tuple(item for item in user_summary if item.get("user_type_id")=="flat_control"), (("condition_id","condition"),("mean_autonomous_minus_yoked_late_delta_rmssd_ms","auto−yoked"),("mean_autonomous_minus_random_late_delta_rmssd_ms","auto−random"),("mean_autonomous_minus_yoked_lagged_same_life_advantage","lagged coupling advantage"),("no_clear_effect_rate","no-clear rate")))}</section>
<section><h2>20. yoked donor map</h2>{_table(yoke_rows, (("condition_id","condition"),("user_type_id","user type"),("target_participant_id","target"),("donor_participant_id","donor"),("target_response_strength_scale","target scale"),("donor_response_strength_scale","donor scale"),("target_physiology_seed","target seed"),("donor_physiology_seed","donor seed"),("hidden_donor","hidden"),("output_sequence_digest","sequence digest")))}</section>
<section><h2>21. invalid / rejected data</h2><p>invalid sessions={len(invalid_sessions)}, invalid/rejected Bundle evaluations={len(rejected_bundles)}。baseline arm不一致もここで診断します。</p>{_table(baseline_diagnostics, (("participant_id","participant"),("condition_id","condition"),("session_index","session"),("reason","reason"),("autonomous_baseline_rmssd_ms","auto"),("yoked_baseline_rmssd_ms","yoked"),("random_baseline_rmssd_ms","random")))}</section>
<section><h2>22. condition比較</h2><p>conditionは明示指定されたものだけです。Stage 8A.2 candidate rankingからの自動採用はありません。</p>{_table(overall, (("condition_id","condition"),("mean_autonomous_minus_yoked_late_delta_rmssd_ms","auto−yoked"),("lower95","lower95"),("upper95","upper95")))}</section>
<section><h2>23. 不確実性</h2><p>participant-level bootstrapとparticipant内session block bootstrapを使用します。短いrunでは区間が広く、insufficient_data/no_clear_effectは正当な結果です。same-type yokedを上回らない場合、個人内追加利益が小さい、type共通系列で十分、session不足、noise増大などが候補です。</p></section>
<section><h2>24. reproduction command</h2><pre><code>{html.escape(reproduction_command)}</code></pre><p>checkpoint: <code>{html.escape(str(manifest.get('checkpoint_path','checkpoint.json')))}</code></p></section>
<section><h2>25. simulation-only注意事項</h2><p class='notice'>本結果は固定好みを持つ仮想参加者によるsimulation diagnosticです。人間での有効性、医療効果、臨床的有意差を主張しません。Wはsession-local監査値であり、異なるbaseline間の主要比較にはΔRMSSDを使用します。hidden preference truthはobserved couplingへ入力していません。</p></section>
<section><h2>相関scatter</h2>{scatter_html}<p class='subtle'>conditionごとのfacetで、点はparticipant-session、色はarm。participant内指標とparticipant横断の点群を区別して解釈してください。</p></section>
<section><h2>Architecture receipt</h2><pre><code>{html.escape(json.dumps(manifest.get('architecture_receipt',{}), ensure_ascii=False, indent=2, sort_keys=True))}</code></pre></section>
"""
    return _page("Stage 8A.3 adaptive placebo RMSSD validation", body)


def write_html_reports(
    run_directory: Path,
    *,
    manifest: Mapping[str, Any],
    conditions: Sequence[ValidationCondition],
    participants: Sequence[Mapping[str, Any]],
    yoke_rows: Sequence[Mapping[str, Any]],
    bundles: Sequence[BundleOutcome],
    sessions: Sequence[SessionOutcome],
    analysis: Mapping[str, Sequence[Mapping[str, Any]]],
    baseline_diagnostics: Sequence[Mapping[str, Any]],
    reproduction_command: str,
) -> tuple[Path, tuple[Path, ...]]:
    report_directory = run_directory / "report"
    participant_directory = report_directory / "participants"
    participant_directory.mkdir(parents=True, exist_ok=True)
    identifiers = sorted({str(item["participant_id"]) for item in participants})
    participant_paths: list[Path] = []
    links: list[tuple[str, str]] = []
    for participant_id in identifiers:
        filename = participant_id + ".html"
        path = participant_directory / filename
        atomic_write_text(
            path,
            _participant_page(
                participant_id,
                conditions,
                bundles,
                sessions,
                analysis.get("paired", ()),
                analysis.get("participant_effects", ()),
            ),
        )
        participant_paths.append(path)
        links.append((participant_id, filename))
    report_path = report_directory / "report.html"
    atomic_write_text(
        report_path,
        build_html_report(
            manifest=manifest,
            conditions=conditions,
            participants=participants,
            yoke_rows=yoke_rows,
            bundles=bundles,
            sessions=sessions,
            analysis=analysis,
            baseline_diagnostics=baseline_diagnostics,
            reproduction_command=reproduction_command,
            participant_links=links,
        ),
    )
    return report_path, tuple(participant_paths)


__all__ = ["build_html_report", "write_html_reports"]
