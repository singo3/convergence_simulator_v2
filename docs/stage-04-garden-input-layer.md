# Stage 4: Garden入力層とセッションシグナル

## 目的

Stage 4は、Stage 3の仮想Polar H10が正式出力するraw RRIをGarden境界で評価し、後続のデジタル生命が受け取れるNと1秒周期のSへ変換する。GUI非依存のcomponentを、Stage 1の決定論的なinteger-microseconds scheduler上でStage 2・3と接続する。

- 実装状態: 完了
- Garden manifest: `relax_with_light_garden_manifest_v0_1`
- input model: `relax_with_light_garden_input_v0_1`
- RRI window membership policy: `measurement_end_time`
- baseline invalid policy: `keep_s_zero_and_skip_main_evaluations`

## 責務

Garden入力層は次を担う。

- `RriMeasurementEvent` のstrict validationとraw RRI受信
- RRI絶対範囲および直近有効RRI中央値によるartifact分類
- 240秒sessionのphase、discard/evaluation window、Sの管理
- 各evaluation window内の有効RRIだけを使うRMSSDの実計算
- 固定式によるN、evaluation quality、session baselineの管理
- NとSを含む1秒周期の `GardenInputSignalEvent`
- 評価結果metadataを含む `GardenEvaluationFinalizedEvent`
- reset可能な診断record、canonical digest、GUI/headless/CSV表示

## 非責務

Stage 4は次を実装しない。

- heartbeatまたはRRIの生成・測定
- 仮想ユーザー内部真値やH10内部recordの参照
- artifact RRIの補正、clip、補間、推定値への置換
- Nd、W、デジタル生命state、Garden出力、光刺激、点滅、ユーザー刺激応答
- P/V比較、勝者・順位決定、閉ループ制御

Ndは後続のデジタル生命、Wは情動系の責務であり、Garden入力層のpayloadや計算へ入れない。

## 正式なevent境界

入力はH10由来の `rri_measurement_event_v1`、すなわち `RriMeasurementEvent` だけである。Garden coreは `VirtualUserComponent`、`HeartbeatRecord`、`PolarH10Component`、`RriMeasurementRecord`、診断CSVを入力にしない。canonical値はinteger microsecondsの `rri_us` とし、event時刻はpayloadの `current_heartbeat_time_us` と一致しなければならない。

正式な1秒シグナルは `garden_input_signal_event_v1` であり、少なくとも次の状態を明示する。

- `signal_time_us`、`signal_index`
- `s`、`phase`、`bundle_index`、`window_role`
- `n_current`、`n_available`
- `n_baseline_session`、`baseline_available`
- `latest_valid_evaluation_id`、`valid_evaluation_revision`
- `session_status`

評価確定時には `garden_evaluation_finalized_event_v1` を出し、window、件数、artifact率、RMSSD、N、quality、reject reason、revisionを記録する。これは評価metadataであり、後続componentへ渡す正式なsession signalはN/Sを持つ `GardenInputSignalEvent` である。

各phase境界では `garden_phase_event_v1` の `GardenPhaseChangedEvent` を出す。phase/evaluation eventはsession進行と評価確定を観測するmetadataであり、N/Sの正式な下流interfaceとは区別する。

## phase、S、時間構造

すべての区間は開始を含み終了を含まない半開区間である。

| 仮想時刻 | phase | role | S | evaluation |
| --- | --- | --- | ---: | --- |
| `[0, 30)` 秒 | `baseline_discard` | discard | 0 | なし |
| `[30, 60)` 秒 | `baseline_evaluation` | evaluation | 0 | baseline |
| `[60, 90)` 秒 | `bundle_0_discard` | discard | 1 | なし |
| `[90, 120)` 秒 | `bundle_0_evaluation` | evaluation | 1 | Bundle 0 |
| `[120, 150)` 秒 | `bundle_1_discard` | discard | 1 | なし |
| `[150, 180)` 秒 | `bundle_1_evaluation` | evaluation | 1 | Bundle 1 |
| `[180, 210)` 秒 | `bundle_2_discard` | discard | 1 | なし |
| `[210, 240)` 秒 | `bundle_2_evaluation` | evaluation | 1 | Bundle 2 |
| `240` 秒以降 | `outside` | outside | 0 | なし |

標準sessionはbaseline 60秒とmain session 180秒で計240秒である。各bundleはdiscard 30秒とevaluation 30秒で構成する。Sはbaseline中0、baselineが有効ならmain session中1、closingの240秒で0になる。0秒から240秒まで1秒間隔で出力するため、標準runの `GardenInputSignalEvent` は241件である。

baselineが無効な場合だけはmain sessionでもSを0に保つ。これは後述するStage 4固有の失敗時policyである。

## RRI artifact

分類順序と境界は固定する。

1. `rri_us < 300_000`: `too_short`
2. `rri_us > 2_000_000`: `too_long`
3. 直近有効historyが5件以上なら、最大15件の中央値 `m` に対して `abs(rri_us - m) / m > 0.20`: `median_deviation`
4. それ以外: valid

300,000 usと2,000,000 usはvalidで、中央値偏差20%ちょうどもvalidである。中央値はcurrent RRIを追加する前のvalid historyから求める。artifactはraw値と理由を記録するが、clipも補間もせず、valid historyおよび評価RMSSDから除外する。

validなdiscard/outside RRIはrolling median historyへ入る。一方、discard/outsideのRRIは評価件数とRMSSDへ入らない。historyはwindowやbundleの境界ではresetせずsession全体で継続し、scenario reset時だけclearする。

## evaluation windowとwindow membership

評価対象は `[30, 60)`、`[90, 120)`、`[150, 180)`、`[210, 240)` の4 windowだけである。RRIの所属は `RriMeasurementEvent.scheduled_time_us`、すなわちmeasurement end timeを半開区間へ当てはめて決める。

- 30秒ちょうど: baseline evaluation
- 60秒ちょうど: Bundle 0 discard
- 90秒ちょうど: Bundle 0 evaluation
- 120秒ちょうど: Bundle 1 discard
- 240秒ちょうど: outside

v2.0は境界をまたぐRRIの所属時刻を規定していないため、この `measurement_end_time` はsimulation implementation assumptionである。詳細は [RRI window membership policy v0.1](rri-window-membership-policy_v0.1.md) を参照する。

## RMSSD

各evaluation windowについて、artifactを除いたRRIをevent時刻順に `r_1, ..., r_K` とする。前windowの最後と現windowの最初の差は使用せず、window内の連続差だけを使う。

```text
RMSSD = sqrt((Σ[i=2..K] (r_i - r_(i-1))^2) / (K - 1))
```

計算はcanonicalなinteger microsecondsで行い、結果だけをmillisecondsへ変換する。有効RRIが2件未満ならRMSSDはnullである。evaluation成立には有効RRIが5件以上必要なので、2〜4件でも最終qualityはrejectedになる。

## qualityとN

window内の受信RRI総数を `M`、artifact数を `A` とし、artifact率を `A / M` とする。`M = 0` の場合は1とする。

- artifact率 `> 0.10`: rejected
- 有効RRI数 `< 5`: rejected
- artifact率 `> 0.05` かつ `<= 0.10`: low confidence
- それ以外: valid

5%ちょうどはvalid、10%ちょうどはlow confidenceであり、low confidenceも有効評価として扱う。rejected reasonは複数同時に保持できる。

有効評価だけ、次の固定式でNを計算する。

```text
N = clip01((RMSSD_ms - 15) / (80 - 15))
  = clip01((RMSSD_ms - 15) / 65)
```

RMSSD 15 ms、47.5 ms、80 msはそれぞれN 0、0.5、1になる。Nの式へsession baseline、以前のN、Nd、Wは入れない。rejected evaluationのNはnullで、`n_current`、baseline、revisionを更新しない。

## baseline

`[30, 60)` のbaseline evaluationがvalidまたはlow confidenceなら、そのNを `n_baseline_session` と `n_current` に設定し、`valid_evaluation_revision` を1にする。session baselineは240秒のsession中固定し、後続bundleのNで変更しない。有効なbundle evaluationは `n_current` とrevisionだけを更新する。

baselineがrejectedの場合は、`n_baseline_session` と `n_current` をnullのままにし、Sを0に保つ。Bundle 0〜2の時刻と評価確定eventは維持するが、各bundleを `skipped_baseline_invalid` を含むrejectedとしてNを更新しない。baselineを再試行せず240秒まで進める。この `keep_s_zero_and_skip_main_evaluations` はv2.0が定めた規範ではなく、Stage 4のsimulation implementation assumptionである。

## 同時刻event ordering

同一仮想時刻では `(scheduled_time_us, priority, sequence)` に従い、次の順序を保証する。

| priority | event |
| ---: | --- |
| 10 | phase change |
| 20 | evaluation finalize trigger |
| 25 | `GardenEvaluationFinalizedEvent` |
| 30 | signal trigger / `GardenInputSignalEvent` |
| 40 | `HeartbeatEvent` |
| 50 | `RriMeasurementEvent` |
| 100 | simulation complete |

したがって60秒ではbaselineがsignalより先に確定し、60秒のsignalは確定済みNとmain-session Sを表す。同時刻60秒のRRIはその後に届き、Bundle 0 discardへ所属する。240秒ではBundle 2評価を確定してからclosing signal S=0を出し、同時刻RRIがあればoutsideとして分類した後に完了する。

## resetと決定性

resetはbaseline/current N、revision、phase/S、artifact median history、evaluation buffer、入力重複検出、RRI/evaluation/signal recordをすべてclearし、immutable configだけを保持する。scenarioはVirtualUser、H10、Gardenをまとめてresetし、固定boundary eventを再登録する。factoryはhandlerを一度だけ登録し、reset後にhandlerやrecordを重複させない。

run-until-end、1秒step、1-event step、速度、batch上限、snapshot頻度、chart表示、CSV export、config JSON round-tripにかかわらずartifact/evaluation/signal/full-event digestは一致する。

## GUI、headless、CSV

GUIの主対象はGarden入力層である。Garden入力tabにはphase/S、RRIとartifact、RMSSD/N、N/S、RRI table、evaluation tableを表示し、仮想ユーザー、Polar H10、時間・event診断tabも維持する。Garden入力層の右側診断領域は縦スクロール可能で、timeline、グラフ、判定表を十分な高さで表示する。GUIはcomponent snapshotとimmutable recordだけを読み、scheduler heapを直接操作しない。

標準240秒scenarioはreal-time待機なしで実行できる。

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-garden-input-demo
```

headless JSONはsession、baseline、N/S、4 evaluation、artifact/evaluation/signal/full-event digestを診断表示するが、Nd、Wや後続Stageの状態は含めない。既存Stage 1〜3 headless JSONは変更しない。

診断CSVは次の3種類である。

- `garden_input_rri_classification_diagnostics.csv`
- `garden_input_evaluations.csv`
- `garden_input_signals.csv`

CSVは観測専用であり、exportの有無はcomponent stateとdigestを変えない。GardenはCSVを正式入力にしない。

## テスト

Stage 4はconfig validation、全phase境界、artifact絶対範囲・中央値境界、history継続、window membership、手計算RMSSD、固定N式、quality境界、baseline有効/無効、bundle更新/reject、N/S schema、同時刻ordering、reset、architecture分離、240秒統合、全execution mode digest、headless、CSV、offscreen GUIを検証する。Stage 1〜3の既存test、CLI、schema、digestも全回帰で維持する。

## 次Stage interface

次工程はデジタル生命とGarden出力層である。後続componentはGarden core内部、diagnostic CSV、scheduler heapではなく、`GardenInputSignalEvent` のN/Sとrevisionを正式interfaceとして受け取る。Stage 4はNd/Wを予約値としても生成せず、Garden出力や光刺激へ先回りしない。
