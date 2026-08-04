# Stage 8A.2 自動条件探索・堅牢候補抽出

Stage 8A.2は`FatigueSigmaSingleConditionRunner`をローカルCPU上で反復実行する上位オーケストレーション層である。simulation core、Digital Life、Runtime、Garden、Stage 8A.1 result schemaを再実装・変更しない。

version:

- model: `fatigue_sigma_auto_search_v0_1`
- strategy: `coarse_refine_confirm_search_v0_1`
- plan: `fatigue_sigma_auto_search_plan_v1`
- job: `fatigue_sigma_auto_search_job_v1`
- manifest: `fatigue_sigma_auto_search_manifest_v1`
- `formal_spec_adoption=false`

## 探索対象

比較する係数は`selected_session_fatigue_target`と`sigma_multiplier`だけである。`p_explore`、`epsilon_accept`、q、P/V/tau、RMSSD→N、`delta_N`、Hash方向、F/T探索、A/D固定、Bundle確認規則は変更しない。固定user type v2の6型を比較し、hidden preferenceはpost-hoc truth alignmentだけに使う。

## 診断

非flat型ではcorrect structureのworst/mean、diffuse、初回構造session、outlier復帰を評価する。`flat_control`ではspurious structure、mechanical rotation、holder switchを安全診断する。全型を通してW ceiling、candidate生成・仮成功・正式採用、sigma実効幅を監査する。割合は95% Wilson interval、連続値はcount/mean/median/min/max/Q1/Q3を併記する。

## 候補

単一総合スコアは作らない。transparent gateとmulti-objective Pareto frontierを保存し、robust compromise、life dominance、BPM common、multi-attractor、low rotation、conservative compromiseを別々に示す。最終gate通過が0件なら`no_robust_candidate`とblockerを出し、係数や結果を自動調整しない。smokeは常に`smoke_diagnostic_only`であり、候補妥当性を主張しない。

## 境界

OpenAI、Codex、ChatGPT、外部LLM、API、network、Qtを使用しない。推薦はsimulationへ戻らず、convergenceで探索を停止しない。moving preference、formal Profile採用、Stage 8Bは実装しない。

関連文書:

- [探索戦略](coarse-refine-confirm-search_v0.1.md)
- [候補選択](robust-candidate-selection_v0.1.md)
- [checkpoint/resume](auto-search-checkpoint-resume_v0.1.md)
- [出力schema](auto-search-output-schemas_v0.1.md)
- [ローカル実行](auto-search-local-execution-guide.md)
