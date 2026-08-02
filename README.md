# 環境共生型デジタル生命シミュレーター v2

環境共生型デジタル生命システムの各componentを、同じ決定論的な仮想時間上で段階的に検証するPythonプロジェクトです。

- Stage 1「時間・イベント配送基盤」: 完成
- Stage 2「外部刺激を受けない仮想ユーザー」: 完成
- Stage 3「仮想Polar H10」: 完成
- Stage 4「Garden入力層とセッションシグナル」: 完成
- Stage 5A「1体のデジタル生命・第1周」: 完成
- 現在のGUI主対象: Stage 5Aの1体のデジタル生命・第1周

正式な信号経路は次のとおりです。

```text
仮想ユーザー
  → HeartbeatEvent
  → 仮想Polar H10
  → RriMeasurementEvent
  → Garden入力層
  → GardenInputSignalEvent (N, S)
  → 1体のデジタル生命
  → 第1周: Nd, W, P, V, B, tau
  → Garden出力層（Stage 5Aでは未接続）
```

仮想ユーザーの正式出力は `HeartbeatEvent` だけです。仮想Polar H10は隣接するheartbeatの正式時刻差をraw RRIとして測定し、RRIを含む `RriMeasurementEvent` だけを正式出力します。H10はartifact判定、RMSSD、N、Nd、Wを扱いません。

Garden入力層は `RriMeasurementEvent` だけをraw inputとし、artifactを除いた評価windowのRRIから実RMSSDとNを求めます。正式な1秒シグナル `GardenInputSignalEvent` はNとSを出力します。Stage 5Aのデジタル生命はこのformal signalと評価metadata eventだけを受け、Nd、W、P、V、B、tauを計算します。

Stage 5AでGとGarden出力層は未接続です。第2周、E/q/kのlive更新、touch配送、3生命の資格競争、光刺激は未実装です。first-round record、GUI、CSVは開発用診断であり、Gardenへの正式出力ではありません。

現在の `ideal_polar_h10_rri_device_v0_1` は、誤差・欠損・遅延なしの理想的な入力デバイスを表すsimulation assumptionです。実機Polar H10のBLE GATT packet、firmware、電波、pairing、Polar SDKを再現するpacket-level emulatorではありません。

## 実装済み

### Stage 1

- integer microsecondsの `SimulationClock`
- deterministic `EventScheduler` と `SimulationEngine`
- `(scheduled_time_us, priority, sequence)` のevent ordering
- pause/resume/reset、1秒step、1-event step、bounded max batch
- QTimerと正式な仮想時計の分離
- 後方互換の20秒time demoとdigest

### Stage 2

- immutable `VirtualUserConfig`
- `baseline_virtual_user_physiology_v0_1`
- SHA-256/Box-Mullerによるstateless named random source
- payloadを `user_id` / `beat_index` だけに限定したheartbeat event
- reset・速度・描画回数に依存しないheartbeat列
- 真のRRI、瞬時HR、rolling RMSSD 30秒、full-run RMSSDの開発用診断
- 仮想ユーザーchart/table、headless JSON、内部真値診断CSV

Stage 2のRRI、RMSSD、内部変動成分は仮想ユーザー内部の開発用診断です。H10測定値またはGarden入力信号として使用しません。

### Stage 3

- immutable `PolarH10Config` と `RriMeasurementRecord`
- GUI非依存の `PolarH10Component`
- `HeartbeatEvent.scheduled_time_us` だけを測定する理想RRI device
- 最初のheartbeatは非出力、2拍目以降は隣接時刻差をraw RRIとして出力
- `heartbeat(40) → rri_measurement(50) → simulation_complete(100)` の同時刻順序
- VirtualUserとH10を接続する共通factoryと決定論的reset
- true RRIとの一致比較、RRI/error chart、最近の測定table
- Stage 3 headless JSONとH10開発診断CSV
- Stage 1・Stage 2のCLI、schema、digestを維持する回帰テスト

### Stage 4

- immutable `GardenInputConfig` と `relax_with_light_garden_input_v0_1`
- GUI非依存の `GardenInputComponent`
- 正式な `RriMeasurementEvent` だけを受けるstrict input boundary
- 300〜2000 msと直近最大15件の有効RRI中央値によるartifact分類
- 30秒evaluation windowごとの実RMSSD、固定式のN、quality判定
- baseline 60秒 + 3 bundle・計180秒の240秒session
- 1秒周期の `GardenInputSignalEvent`（N、S）と評価確定event
- baseline固定、rejected評価のN非更新、baseline無効時の明示policy
- Garden入力GUI、240秒headless JSON、3種類の診断CSV、決定論的digest
- Stage 1〜3のCLI、schema、digestを維持する回帰テスト

### Stage 5A

- immutable `DigitalLifeConfig` とred/green/blueの3つのsimulation fixture
- GUI非依存の `SingleDigitalLifeComponent`
- `GardenInputSignalEvent` と `GardenEvaluationFinalizedEvent` だけを受けるformal boundary
- baseline相対Nd、独立した情動評価W、`Phi_P` によるP
- Stage 5A中は保持するE=0/q=0.5、N/q/EからのV
- 固定kと生命固有 `Phi_B`、論理到達値tau
- baseline/revision/rejected評価の一回限りの適用と240秒closing処理
- 1体のデジタル生命GUI、240秒headless JSON、2種類の開発診断CSV
- Stage 4のevent stream/digestとStage 1〜4のCLI/schema/CSVを維持する回帰テスト

## Requirements / setup

- Python 3.12以上
- PySide6 / Qt Widgets
- PyQtGraph / NumPy
- pytest / pytest-qt
- Ruff

Stage 5A固定検証環境はPython 3.13.4、PySide6 6.11.1、PyQtGraph 0.14.0、NumPy 2.5.1、pytest 9.1.1、pytest-qt 4.5.0、Ruff 0.16.1です。

プロジェクト直下の `.venv` をStage間で再利用します。

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
```

## GUI起動

```bash
.venv/bin/python -m symbiotic_sim_v2
```

macOSでは、汎用launcher `環境共生型デジタル生命シミュレーターv2を起動.command` をダブルクリックできます。`時間シミュレーターを起動.command` も後方互換用に維持しています。

GUI上部にはStage 1共通の時計、状態、速度、step controlsがあります。中央のtabは次の5つです。

1. デジタル生命: N/baseline/Nd/W、P/V/tau、E/q、k/B、1秒signal・評価table
2. Garden入力層: phase/S、RRI/artifact、RMSSD/N、N/S、RRI・評価table
3. 仮想ユーザー: Stage 2設定、内部真値の開発用診断
4. Polar H10: ideal mode固定条件、raw RRI、真値比較、誤差、測定table
5. 時間・イベント診断: timeline、実行済みevent log、wall/virtual time診断

仮想ユーザー設定とDigital Life roleは開始前またはreset後だけ変更できます。Digital Life roleはred/green/blue、標準はgreenです。H10にはnoise、latency、packet loss、artifact rateなどの調整parameterはありません。Garden入力のモデル値とpolicyは固定設定として表示し、GUIからscheduler内部heapを操作しません。

## Headless

Stage 1 time demo（後方互換）:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-demo
.venv/bin/python -m symbiotic_sim_v2 --headless-time-demo
```

Stage 2標準180秒scenario:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-virtual-user-demo
```

Stage 3標準180秒scenario:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-h10-demo
```

Stage 4標準240秒scenario:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-garden-input-demo
```

Stage 5A標準greenの240秒scenario:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-single-life-demo
```

red/green/blueのroleを指定できます。

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-single-life-demo --life-role blue
```

いずれもreal-time待機をせずJSONを標準出力します。package versionはStage 5Aとして `0.5.0` です。ただし既存JSON contractを変えないため、`--headless-h10-demo` の `project_version` は `0.3.0`、`--headless-garden-input-demo` は `0.4.0` を意図的に維持します。

既存Stage 1〜4 JSONは変更しません。Stage 3 JSONはraw RRI統計、一致比較、heartbeat/measurement/full-event digestを分離し、RMSSD、N、Nd、W、artifact評価を含めません。Stage 4 JSONはGardenのsession、N/S、4評価、artifact/evaluation/signal/full-event digestを診断表示し、NdとWを含めません。Stage 5A JSONは生命config、生得値、最終第1周値、first-round/evaluation-update/full-event digestと `G_status=not_connected` を表示し、actual G値、holder、touch order、実際のGarden出力を含めません。

## 開発用CSV export

Stage 2の仮想ユーザー内部真値:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-virtual-user-demo --export-virtual-user-csv virtual_user_true_heartbeat_diagnostics.csv
```

Stage 3のH10 raw測定と独立診断比較:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-h10-demo --export-h10-csv polar_h10_rri_measurement_diagnostics.csv
```

Stage 4 Garden入力層はGUIとheadless helperから次の3種類を保存できます。

- `garden_input_rri_classification_diagnostics.csv`
- `garden_input_evaluations.csv`
- `garden_input_signals.csv`

headlessで3ファイルを同じdirectoryへ保存する例:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-garden-input-demo \
  --export-garden-input-csv artifacts/csv/stage-04
```

Stage 5AのDigital LifeはGUIとheadless helperから次の2種類を保存できます。

- `single_digital_life_first_round_diagnostics.csv`
- `single_digital_life_evaluation_updates.csv`

headlessで2ファイルを保存する例:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-single-life-demo \
  --export-single-life-csv artifacts/csv/stage-05a
```

GUIからも診断CSVを保存できます。H10 CSVのraw device output列と `diagnostic_true_rri_*` / `absolute_error_us` / `match` 列は責務上分離され、`diagnostic_notice` 列で開発用比較であることを明示します。GardenはCSVではなく `RriMeasurementEvent` を直接受信し、Digital LifeもCSVではなくGarden formal eventを受信します。CSV exportの有無はsimulation結果とdigestを変えません。

## Formal event boundaries

`HeartbeatEvent`:

```json
{
  "event_type": "heartbeat",
  "source": "virtual_user",
  "priority": 40,
  "scheduled_time_us": 855679,
  "payload": {
    "user_id": "virtual-user-001",
    "beat_index": 1
  }
}
```

`RriMeasurementEvent`:

```json
{
  "event_type": "rri_measurement",
  "source": "polar_h10",
  "priority": 50,
  "scheduled_time_us": 855679,
  "payload": {
    "device_id": "polar-h10-sim-001",
    "user_id": "virtual-user-001",
    "measurement_index": 0,
    "previous_beat_index": 0,
    "current_beat_index": 1,
    "previous_heartbeat_time_us": 0,
    "current_heartbeat_time_us": 855679,
    "rri_us": 855679,
    "rri_ms": 855.679,
    "event_schema_version": "rri_measurement_event_v1"
  }
}
```

`rri_us` がcanonicalな値で、`rri_ms` は導出値です。H10 payloadへtrue RRI、RMSSD、N/Nd/W、artifact、内部生理成分を入れません。

Garden入力層はこの `RriMeasurementEvent` だけを受け、1秒周期の `GardenInputSignalEvent` に `n_current` と `s` を載せます。評価確定時の件数、artifact率、RMSSD、N、qualityは `GardenEvaluationFinalizedEvent` へ記録します。正式なsignal payloadにNdとWはありません。

Stage 5A Digital Lifeの正式入力はこの `GardenInputSignalEvent` と `GardenEvaluationFinalizedEvent` だけです。N/Sはsignalからのみ取得し、evaluation eventはID/quality/revisionの由来metadataとして使用します。Gardenのcomponent/record、RRI、RMSSD、artifact内部値を参照しません。Stage 5A Digital Lifeに正式外部出力eventはなく、first-round/evaluation-update recordは開発用診断です。

## Stage 4 Garden input model

### 時間構造とS

| 仮想時刻 | role | S（baseline有効時） | evaluation |
| --- | --- | ---: | --- |
| `[0, 30)` 秒 | baseline discard | 0 | なし |
| `[30, 60)` 秒 | baseline evaluation | 0 | baseline |
| `[60, 90)` 秒 | Bundle 0 discard | 1 | なし |
| `[90, 120)` 秒 | Bundle 0 evaluation | 1 | Bundle 0 |
| `[120, 150)` 秒 | Bundle 1 discard | 1 | なし |
| `[150, 180)` 秒 | Bundle 1 evaluation | 1 | Bundle 1 |
| `[180, 210)` 秒 | Bundle 2 discard | 1 | なし |
| `[210, 240)` 秒 | Bundle 2 evaluation | 1 | Bundle 2 |
| `240` 秒 | closing/outside | 0 | なし |

baselineは30秒discard + 30秒evaluationです。各bundleも30秒discard + 30秒evaluationで、3 bundleのmain sessionは180秒、全体は240秒です。0〜240秒を1秒間隔で出力するため、標準runのN/S signalは241件です。

### RRI artifact

分類は次の順序です。

1. `rri_us < 300_000`: `too_short`
2. `rri_us > 2_000_000`: `too_long`
3. 有効historyが5件以上なら、直近最大15件の中央値からの偏差が20%を超える値: `median_deviation`
4. それ以外: valid

300〜2000 msの両端と偏差20%ちょうどはvalidです。artifactはraw値のまま記録し、clipも補間もせず、valid historyと評価RMSSDから除外します。validなdiscard/outside RRIは中央値historyへ入りますが、評価windowのRMSSDには使いません。historyはwindow境界でresetしません。

### RMSSD、N、quality

各evaluation window内の有効RRIを時刻順に `r_1, ..., r_K` とすると、RMSSDは次の実計算です。前windowとの境界差は含めません。

```text
RMSSD = sqrt((Σ[i=2..K] (r_i - r_(i-1))^2) / (K - 1))
```

canonicalなmicrosecondsで計算して結果をmillisecondsへ変換し、2件未満ならnullです。有効RRIが5件未満、またはartifact率が10%を超えるevaluationはrejectedです。artifact率が5%を超え10%以下ならlow confidence、それ以下ならvalidです。5%ちょうどはvalid、10%ちょうどはlow confidenceです。

validまたはlow-confidence evaluationのNはbaselineを入力にせず、固定式だけで計算します。

```text
N = clip01((RMSSD_ms - 15) / (80 - 15))
  = clip01((RMSSD_ms - 15) / 65)
```

baseline evaluationが有効ならそのNを `n_baseline_session` と `n_current` に設定し、session中のbaselineは固定します。以後の有効bundle評価はcurrent Nだけを更新します。rejected評価ではN、baseline、revisionを更新しません。

### 明示的なimplementation policies

v2.0は境界をまたぐRRIの所属を明示していません。Stage 4は `measurement_end_time`、すなわち `RriMeasurementEvent.scheduled_time_us` を半開区間へ当てはめます。30秒ちょうどはbaseline evaluation、60秒ちょうどはBundle 0 discard、240秒ちょうどはoutsideです。これはsimulation implementation assumptionです。

v2.0はbaseline無効時のretryを規定していません。Stage 4は `keep_s_zero_and_skip_main_evaluations` を採用し、S=0とN=nullを維持したまま240秒まで進め、main evaluationsをrejectedとしてNを更新しません。これもsimulation implementation assumptionです。

## Stage 5A Digital Life first-round model

新しい有効evaluation revisionを受けたときだけ、Garden signalのNと固定session baselineからNdを更新し、情動系がWを評価します。MVPで値は `W=Nd` ですが、別概念・別fieldです。

```text
Nd = clip01(0.5 + (N_current - N_baseline_session) / (2 * 0.10))
P  = 1 - S * (1 - p_intrinsic)
V  = clip01(((N_current + q) / 2) * (1 - E))
B  = Phi_B(k_current)
tau = clip01(P / (P + V + 0.000001) + birth_phase)  # S=1のみ
```

Stage 5AでE=0、q=0.5、`k_current=[0.5,0.5,0.5,0.5]` をlive更新しません。S=0でP=1、tau=nullです。240秒closingではBundle 2 revisionをNd/Wへ先に適用した後、S=0のP/tauを記録します。Gは `not_connected`、touch配送は0件です。

## Deterministic digest baselines

- Stage 1: `1c4217065fa29316e7ead83c4d604e87f9fe8fe46e82b689b5566dbc9890598d`
- Stage 2 heartbeat: `4c039f5f1b5cc3cd78682cca890a8a6ec70510a52b4ad4addeabcb0ecd3ae765`
- Stage 2 diagnostic: `ef0bc8c644e8b5f6fc2c3b58ef825491e49e005bc0c6c22a9f0c62c66168cd8f`
- Stage 2 full event: `761a2dc6b2b03c4d538a85d95160f2ecc731e301a1362006ee97ea575872bddb`

Stage 3 measurement digestは `scheduled_time_us` とcanonicalな `rri_us` を含み、導出可能な `rri_ms` とscheduler識別子 `event_id` を除外します。

Stage 4はRRI artifact分類、4 evaluation、241件のN/S signal、full event列をそれぞれcanonical JSON化したdigestを分離します。固定値をREADMEへ重複記載せず、headless結果と回帰testをsource of truthとします。実行mode、reset、snapshot・chart頻度、CSV export、config JSON round-tripはdigestを変えません。

Stage 5Aは241件のfirst-round recordと、新しい有効評価またはrejected評価に対応するevaluation-update recordのdigestを分けます。Digital Lifeは新規eventを発行しないため、Stage 4とStage 5Aのfull event digestは同じです。roleを変えてもVirtualUser/H10/Gardenの結果は不変で、生命固有のP/B/tauとfirst-round digestだけが変化します。

## Test / lint / smoke

```bash
.venv/bin/python -m compileall -q src tests
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q
.venv/bin/ruff check .
QT_QPA_PLATFORM=offscreen .venv/bin/python -m symbiotic_sim_v2 --smoke-test --auto-close-ms 3500
```

テストはStage 1〜4全回帰に加え、Digital Life config、Hash01、Nd/W/P/V/B/tauのpure function、formal event boundary、baseline/revision/reject/240秒closing、role fixture、reset、全execution mode digest、headless、CSV、offscreen GUI、architecture分離を確認します。

Stage 5Aの設計境界は [1体のデジタル生命・第1周](docs/stage-05a-single-digital-life-first-round.md)、式と分類は [Digital Life first-round model v0.1](docs/digital-life-first-round-model_v0.1.md) を参照してください。Stage 4の設計境界は [Garden入力層設計](docs/stage-04-garden-input-layer.md)、モデル値は [Garden input model v0.1](docs/relax-with-light-garden-input-model_v0.1.md)、境界所属の仮定は [RRI window membership policy v0.1](docs/rri-window-membership-policy_v0.1.md) にあります。規範との境界は [規範スコープ](docs/normative-scope.md) を参照してください。

次工程は **Stage 5B: 3生命とGarden資格競争・第2周** です。Stage 5Aは1体の第1周までを実装し、G、Garden出力層、touch配送、E/q/k更新、holder/勝者/順位を先回り実装していません。3 bundle関係記憶探索は後続のStage 5Cです。
