# Relax with Light Garden input model v0.1

## Versionと位置づけ

- model version: `relax_with_light_garden_input_v0_1`
- manifest version: `relax_with_light_garden_manifest_v0_1`
- formal input schema: `rri_measurement_event_v1`
- formal signal schema: `garden_input_signal_event_v1`
- evaluation schema: `garden_evaluation_finalized_event_v1`
- phase schema: `garden_phase_event_v1`

本書はStage 4で固定したGarden入力層の再現可能なモデル仕様である。規範仕様v2.0から参照した値と、v2.0が定めていないsimulation implementation assumptionを分離する。規範仕様そのものを置き換える文書ではない。

## v2.0から参照する値と責務

Relax with Light Garden入力層について、次をv2.0の参照値・責務として実装する。

- 入力デバイスH10の正式出力はRRI
- Garden入力層はRRIからartifact、RMSSD、N、baseline、Sを扱う
- RRI絶対範囲: 300〜2000 ms（両端を含む）
- 直近有効RRI中央値からの相対偏差: 20%を超えるとartifact
- artifact率: 5%を超えるとlow confidence、10%を超えるとreject
- evaluation成立に必要な有効RRI数: 5件以上
- N正規化範囲: RMSSD 15〜80 ms
- baseline: discard 30秒 + evaluation 30秒
- main session: 3 bundle、各bundleはdiscard 30秒 + evaluation 30秒
- セッションシグナル: 1秒周期

window境界をまたぐRRIの所属規則、およびbaseline無効時の再試行・後続評価policyはv2.0に明示がない。これらは後述のversion付き実装仮定である。

## 固定config

`GardenInputConfig` はimmutableで、strict JSON round-tripを提供する。標準値は次のとおりである。

| field | value |
| --- | ---: |
| `garden_id` | `relax-with-light` |
| `signal_interval_us` | `1_000_000` |
| `baseline_discard_seconds` | `30` |
| `baseline_evaluation_seconds` | `30` |
| `main_session_seconds` | `180` |
| `bundle_count` | `3` |
| `bundle_discard_seconds` | `30` |
| `bundle_evaluation_seconds` | `30` |
| `rri_min_us` | `300_000` |
| `rri_max_us` | `2_000_000` |
| `median_history_min_valid_count` | `5` |
| `median_history_max_valid_count` | `15` |
| `median_relative_deviation_limit` | `0.20` |
| `low_confidence_artifact_rate` | `0.05` |
| `reject_artifact_rate` | `0.10` |
| `minimum_valid_rri_count` | `5` |
| `rmssd_min_ms` | `15.0` |
| `rmssd_max_ms` | `80.0` |
| `rri_window_membership_policy` | `measurement_end_time` |
| `baseline_invalid_policy` | `keep_s_zero_and_skip_main_evaluations` |

時間、件数、閾値、version、schemaの整合をconfig生成時に検証する。boolを整数として受理せず、非有限float、missing/unknown field、version不一致を拒否する。canonicalな時間とRRIはinteger microsecondsで保持する。

## RRI artifact規則

入力は `RriMeasurementEvent` のraw `rri_us` であり、次の優先順で分類する。

1. `rri_us < 300_000` は `too_short`
2. `rri_us > 2_000_000` は `too_long`
3. current RRIを含める前の直近有効RRIが5件以上なら、最大15件の中央値 `m` を求める
4. `abs(rri_us - m) / m > 0.20` は `median_deviation`
5. それ以外はvalid

絶対範囲の両端と相対偏差20%ちょうどはvalidである。artifactはraw値のまま診断recordへ残し、clip・補間・置換をしない。artifactをvalid historyへ追加せず、評価RMSSDから除外する。

validなdiscard/outside RRIは、後続RRIを分類するrolling valid historyには追加する。ただしevaluation windowのRRI集合には追加しない。historyはbaseline/bundle/window境界でclearせず、session reset時だけclearする。

## evaluation windowとRMSSD

RMSSDは4つのevaluation window `[30, 60)`、`[90, 120)`、`[150, 180)`、`[210, 240)` ごとに独立して計算する。各window内でartifactでないRRIをevent時刻順に並べ、canonical microsecondsの値を `r_1, ..., r_K` とする。

```text
RMSSD_us = sqrt((Σ[i=2..K] (r_i - r_(i-1))^2) / (K - 1))
RMSSD_ms = RMSSD_us / 1000
```

window間をまたぐ連続差、discard/outside RRI、artifact RRIは使わない。`K < 2` ならRMSSDはnullである。

RRIのwindow所属には `measurement_end_time` を使う。このpolicyはv2.0参照値ではなく、[RRI window membership policy v0.1](rri-window-membership-policy_v0.1.md) に定義するsimulation implementation assumptionである。

## N

有効なevaluationのRMSSDだけを、baseline非依存の固定式へ入力する。

```text
N = clip01((RMSSD_ms - 15) / 65)
clip01(x) = min(1, max(0, x))
```

| RMSSD | N |
| ---: | ---: |
| 15 ms以下 | 0 |
| 47.5 ms | 0.5 |
| 80 ms以上 | 1 |

session baseline、過去N、Nd、WはNの計算式へ入れない。rejected evaluationは `n = null` であり、保持中のNを更新しない。

## evaluation quality

window内で受信したRRI総数を `M`、そのうちartifact件数を `A` とする。artifact率は `M > 0` なら `A / M`、`M = 0` なら1である。

- `A / M > 0.10`: `rejected`
- valid RRI数 `< 5`: `rejected`
- 上記reject条件がなく `A / M > 0.05`: `low_confidence`
- それ以外: `valid`

5%ちょうどはvalid、10%ちょうどはlow confidenceである。`valid` と `low_confidence` は `is_valid = true`、`rejected` はfalseとする。`no_rri`、`artifact_rate_exceeded`、`insufficient_valid_rri`、`skipped_baseline_invalid` など、成立するreject reasonを複数保持する。

## baseline scopeと更新規則

baseline evaluationがvalidまたはlow confidenceなら、そのNを一度だけ `n_baseline_session` に固定し、同時に `n_current` へ設定する。`valid_evaluation_revision` は1となる。

Bundle 0〜2の有効評価は `n_current` とrevisionを更新するが、`n_baseline_session` は変更しない。bundle evaluationがrejectedなら、その評価recordのNはnullとし、`n_current`、baseline、revisionをすべて維持する。

baselineがrejectedなら、baseline/current Nをnull、revisionを0、Sを0のまま維持する。240秒sessionは止めず、3つのmain evaluationを `skipped_baseline_invalid` として確定するが、Nを更新しない。baseline retryは行わない。この `keep_s_zero_and_skip_main_evaluations` は **simulation implementation assumption** であり、v2.0に規定された失敗時動作ではない。

## Sとoutput signal

Sは時刻構造とbaseline availabilityから決まる。

- 0〜60秒未満のbaseline: S=0
- 60〜240秒未満のmain session: baselineが有効ならS=1、無効ならS=0
- 240秒のclosingおよびoutside: S=0

標準sessionでは0秒から240秒まで1秒ごとに241件の `GardenInputSignalEvent` を出す。signalはphase、S、current N、fixed session baseline、availability、最新有効evaluation ID、revision、session statusを持つ。Nは評価確定時だけ変化し、次の有効評価まで同じ値を保持する。

評価ごとの件数、artifact率、RMSSD、N、qualityは `GardenEvaluationFinalizedEvent` で通知する。NdとWはどちらのpayloadにも含めない。

## 既知の制約

- `measurement_end_time` は境界所属の実装仮定であり、RRI start time、midpoint、overlap weightingは未実装である。
- `keep_s_zero_and_skip_main_evaluations` はbaseline無効時の実装仮定であり、retry、延長、fallback baselineは未実装である。
- artifact処理は固定の絶対範囲とrolling medianだけであり、補間、ectopic beat修正、signal quality indexは実装しない。
- 標準sessionは単一user、単一H10、単一Garden、240秒固定である。
- Stage 4はNd、W、デジタル生命、Garden出力、光刺激、閉ループを実装しない。
- GUI/CSV/headlessの内部診断値は正式な後続signalではない。後続Stageは `GardenInputSignalEvent` をinterfaceとして使用する。
