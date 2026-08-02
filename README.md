# 環境共生型デジタル生命シミュレーター v2

環境共生型デジタル生命システムの各componentを、同じ決定論的な仮想時間上で段階的に検証するPythonプロジェクトです。

- Stage 1「時間・イベント配送基盤」: 完成
- Stage 2「外部刺激を受けない仮想ユーザー」: 完成
- Stage 3「仮想Polar H10」: 完成
- Stage 4「Garden入力層とセッションシグナル」: 完成
- Stage 5A「1体のデジタル生命・第1周」: 完成
- Stage 5B「3生命・資格競争・第2周」: 完成
- Stage 5B.1「Garden出力境界・qualified B実効時刻補正」: 完成
- Stage 6「Garden Light Mapper・仮想光点滅device」: 完成
- 現在のGUI主対象: Stage 6のB→I、連続位相、光stimulus segment診断

正式な信号経路は次のとおりです。

```text
仮想ユーザー
  → HeartbeatEvent
  → 仮想Polar H10
  → RriMeasurementEvent
  → Garden入力層
  → GardenInputSignalEvent (N, S)
  → red / green / blueの独立した第1周: Nd, W, P, V, B, tau
  → 各tauを個別touch時刻へ写像
  → DigitalLifeTouchEvent (ID, B)
  → Garden出力資格層（actual arrivalでholder決定・保持）
  → GardenQualifiedBEvent v2（holder touchと同じeffective time）
  → Garden Light Mapper（Hue=360F, BPM=10+155T）
  → LightCommandEvent = I
  → Virtual PC Light Device（continuous sine phase）
  → LightStimulusStateEvent（Stage 7正式境界）
  → round finalize（全touch確認・feedback同期）
  → holder ID + 各生命自身のB
  → 各生命の第2周: G, E, q（k固定）
```

仮想ユーザーの正式出力は `HeartbeatEvent` だけです。仮想Polar H10は隣接するheartbeatの正式時刻差をraw RRIとして測定し、RRIを含む `RriMeasurementEvent` だけを正式出力します。H10はartifact判定、RMSSD、N、Nd、Wを扱いません。

Garden入力層は `RriMeasurementEvent` だけをraw inputとし、artifactを除いた評価windowのRRIから実RMSSDとNを求めます。正式な1秒シグナル `GardenInputSignalEvent` はNとSを出力します。Stage 5Aのデジタル生命はこのformal signalと評価metadata eventだけを受け、Nd、W、P、V、B、tauを計算します。

Stage 5BではG、E/q第2周、touch配送、3生命の資格競争を接続しました。Stage 5B.1では生命由来touchをID/Bだけのv2境界へ絞り、active qualified Bをholder touchの実到着時刻に出力します。Stage 6はこのformal eventだけを入力に、FをHue、Tをblink BPMへ写像し、仮想時計から連続sine位相を解析的に再構成します。A/Dは監査用source Bに残しますが光parameterへは使いません。光に反応するVirtualUserとStage 5Cの関係記憶探索はまだ実装していません。

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

### Stage 5B

- red / green / blueの独立stateと同じGarden N/Sの個別演算
- `three_digital_life_runtime_v0_2` とtauのinteger-microseconds個別配送
- role/P/V/tauを含めずID/Bだけを運ぶ `digital_life_touch_event_v2`
- actual arrivalだけによるholder assignment、S=1中の保持、closing第2周後の解放
- recipient自身のBだけを返す `garden_interoceptive_feedback_event_v1`
- 各生命内のID照合によるG、毎signalのE更新、新規有効BundleかつG=1だけのq更新
- 全生命で固定kと `deferred_to_stage_5c`
- 次Stage境界の `garden_qualified_b_event_v2`（Hue/BPM/Iは未実装）
- 6 tab GUI、240秒headless JSON、4種類のCSV、5種類のStage 5B digest
- Stage 1〜5A CLI/schema/digest/CSVを維持する回帰テスト

### Stage 5B.1

- Runtime/session rosterからGardenへ参加IDを注入し、Garden coreの固定ID→role表を除去
- `qualified_b_on_holder_touch_v0_1` によりactive Bをholder touchと同じmicrosecond・priority 65で出力
- `effective_time_us` をqualified B v2のformal payloadと診断recordへ明示
- inactive commandはsignal time、active commandはcurrent signalのholder touch Bを使用
- round finalizeはqualified Bを再出力せず、全touch確認・feedback・第2周同期だけを担当
- touch order、holder、G、E、q、k、feedback時刻、closing releaseをStage 5Bから維持

### Stage 6

- `relax_with_light_b_to_i_mapper_v0_1`、`relax_with_light_pc_hsv_sine_mapping_v0_1`、`light_command_event_v1`
- `Hue=360F`、`blink_BPM=10+155T`、Saturation 100%、Value 35〜50%のsine波
- A/Dはsource Bとして保存するが光parameterへ不使用
- `virtual_pc_light_device_v0_1` とabsolute virtual-timeのcontinuous phase
- same command/Hue/BPM変更時のphase継続、inactive後のactiveだけreset
- `continuous_phase_integrator_v0_1`、`hold_until_next_command_v0_1`、`light_off_black_v0_1`
- 半開区間 `light_stimulus_segment_v1` と `fixed_virtual_grid_20ms_v0_1` 診断
- Stage 7正式境界 `light_stimulus_state_event_v1`
- 20ms固定virtual grid診断、headless JSON、4種類CSV、7タブGUI
- GUI previewは校正済み物理光でなく、光はまだHeartbeat/RRIを変えない

## Requirements / setup

- Python 3.12以上
- PySide6 / Qt Widgets
- PyQtGraph / NumPy
- pytest / pytest-qt
- Ruff

Stage 6固定検証環境はPython 3.13.4、PySide6 6.11.1、PyQtGraph 0.14.0、NumPy 2.5.1、pytest 9.1.1、pytest-qt 4.5.0、Ruff 0.16.1です。

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

GUI上部にはStage 1共通の時計、状態、速度、step controlsがあります。中央のtabは次の7つです。

1. 光点滅シミュレーター: current HSV/phase、opt-in preview、waveform、parameter、command/segment表。previewは初期OFFで、10倍・100倍・最速では自動OFF
2. 3生命・資格競争: 3状態card、tau/touch、G/holder、E/q、P/V、B、touch/第2周table
3. Garden出力資格層: holder timeline、資格規則、qualified B、qualification table
4. Garden入力層: phase/S、RRI/artifact、RMSSD/N、N/S、RRI・評価table
5. 仮想ユーザー: Stage 2設定、内部真値の開発用診断
6. Polar H10: ideal mode固定条件、raw RRI、真値比較、誤差、測定table
7. 時間・イベント診断: timeline、実行済みevent log、wall/virtual time診断

仮想ユーザー設定は開始前またはreset後だけ変更できます。Stage 5Aの1体専用GUI/role fixtureも後方互換として残します。H10にはnoise、latency、packet loss、artifact rateなどの調整parameterはありません。Garden入力・出力のモデル値とpolicyは固定設定として表示し、GUIからscheduler内部heapを操作しません。

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

Stage 5Bの3生命・資格競争・第2周:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-three-life-competition-demo
```

Stage 6のGarden Light Mapper・仮想光device:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-light-device-demo
```

いずれもreal-time待機をせずJSONを標準出力します。package versionは `0.7.0` です。既存JSON contractを変えないため、Stage 3/4/5A/5B.1 headlessの `project_version` はそれぞれ `0.3.0`、`0.4.0`、`0.5.0`、`0.6.1` を意図的に維持します。

既存Stage 1〜5A JSONは変更しません。Stage 5B JSONはholder、生命別E/q/G/k、touch/feedback/qualified B件数と分離digestを表示し、探索状態、Hue、BPM、I、光波形を含めません。

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

Stage 5Bは次の4ファイルを保存します。

- `stage_05b_digital_life_touches.csv`
- `stage_05b_garden_qualification.csv`
- `stage_05b_qualified_b_outputs.csv`
- `stage_05b_digital_life_second_round.csv`

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-three-life-competition-demo \
  --export-three-life-competition-csv artifacts/csv/stage-05b
```

Stage 6は次の4ファイルを保存します。

- `stage_06_light_commands.csv`
- `stage_06_light_stimulus_states.csv`
- `stage_06_light_stimulus_segments.csv`
- `stage_06_light_waveform_samples_20ms.csv`

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-light-device-demo \
  --export-light-device-csv artifacts/csv/stage-06
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

Stage 5B.1の正式touch v2はID、signal識別metadata、Bだけを含み、role、P、V、tauは含みません。参加IDはRuntime/session rosterからGardenへ注入され、Garden coreはroleを参照せずactual arrival orderだけでholderを決めます。active `GardenQualifiedBEvent` v2はholder touchの実到着時刻を `effective_time_us` として同じmicrosecondに出力され、round finalizeでは再出力されません。Stage 6 Mapperはこのeventだけから `LightCommandEvent=I` を作り、Deviceは同時刻の `LightStimulusStateEvent` と半開区間segmentを作ります。各生命へのfeedbackと第2周は従来どおりround finalize後です。

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

## Stage 5B competition and second-round model

3生命は同じN/Sを受けますが互いの内部値を参照しません。Runtimeは各tauを個別touch時刻へ写像するだけで、Gardenがactual arrivalからholderを決めます。holderはS=1中固定ですが全生命が毎signal touchします。active qualified Bはそのsignalのholder touch時刻から有効で、round finalizeは全touchを確認してfeedbackと第2周を同期します。各生命はID照合でGを計算し、毎signal Eを更新し、新規有効Bundle評価かつG=1だけqを更新します。更新E/qは次signalから使用し、kは固定です。240秒ではinactive commandを出し、Bundle 2を解放前holderへ帰属してからreleaseします。

## Stage 6 B→I and virtual light model

Stage 6のMapperは `GardenQualifiedBEvent v2` だけを受け、`Hue=360F`、`BPM=10+155T`、Saturation=1.0、Value=`0.425+0.075sin(2πphase)` の `LightCommandEvent` を生成します。A/Dはsource Bとして保存しますが光parameterに使いません。

F=1のformal Hueは360.0のまま保持します。render Hueの0.0へのmodulo、event priority/schema、位相開始・継続、command hold、inactive black、segment、20ms sampling、GUI previewは、v2.0が具体化していないStage 6のversion管理されたsimulation implementation assumptionです。

Virtual Light Deviceはcommandを次commandまで保持し、integer microsecondsのabsolute virtual timeからphase/Valueを解析的に求めます。same commandやBPM/Hue変更でphaseをresetせず、inactiveからactiveのみphase 0へresetします。inactiveは黒、formal outputは `LightStimulusStateEvent`、監査記録は半開区間 `LightStimulusSegment` です。

## Deterministic digest baselines

- Stage 1: `1c4217065fa29316e7ead83c4d604e87f9fe8fe46e82b689b5566dbc9890598d`
- Stage 2 heartbeat: `4c039f5f1b5cc3cd78682cca890a8a6ec70510a52b4ad4addeabcb0ecd3ae765`
- Stage 2 diagnostic: `ef0bc8c644e8b5f6fc2c3b58ef825491e49e005bc0c6c22a9f0c62c66168cd8f`
- Stage 2 full event: `761a2dc6b2b03c4d538a85d95160f2ecc731e301a1362006ee97ea575872bddb`

Stage 3 measurement digestは `scheduled_time_us` とcanonicalな `rri_us` を含み、導出可能な `rri_ms` とscheduler識別子 `event_id` を除外します。

Stage 4はRRI artifact分類、4 evaluation、241件のN/S signal、full event列をそれぞれcanonical JSON化したdigestを分離します。固定値をREADMEへ重複記載せず、headless結果と回帰testをsource of truthとします。実行mode、reset、snapshot・chart頻度、CSV export、config JSON round-tripはdigestを変えません。

Stage 5Aは241件のfirst-round recordと、新しい有効評価またはrejected評価に対応するevaluation-update recordのdigestを分けます。Digital Lifeは新規eventを発行しないため、Stage 4とStage 5Aのfull event digestは同じです。roleを変えてもVirtualUser/H10/Gardenの結果は不変で、生命固有のP/B/tauとfirst-round digestだけが変化します。

Stage 5B.1はtouch、qualification、qualified B、feedback、生命別second roundを別々にdigest化します。標準runはtouch 540、feedback 723、active/inactive output 180/61、assignment/release各1です。touch/qualified B/full event digestはv2 schemaと補正時刻を反映し、qualification/feedback/second roundの意味は維持します。run-to-end、step、速度、reset、snapshot頻度、GUI、CSV exportは結果を変えません。

Stage 6はcommand、stimulus state、segment、20ms fixed-grid waveform、full eventを分離digest化します。標準runは241 command/state、240 segment、12001 sampleで、run mode、reset、snapshot頻度、GUI preview、CSV exportに対して同一です。固定値は [Stage 6 reference vectors](docs/conformance/stage-06-reference-vectors.json) をsource of truthとし、[Stage 6設計文書](docs/stage-06-light-blink-simulator.md) に監査用一覧を記載します。

## Test / lint / smoke

```bash
.venv/bin/python -m compileall -q src tests tools
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q
.venv/bin/ruff check .
QT_QPA_PLATFORM=offscreen .venv/bin/python -m symbiotic_sim_v2 --smoke-test --auto-close-ms 5500
```

テストはStage 1〜5B.1全回帰に加え、strict B→I境界、連続phase、command equivalence、state query、segment、fixed sampling、digest、headless、CSV、7-tab GUI、architecture分離を確認します。

Stage 5Aの設計境界は [1体のデジタル生命・第1周](docs/stage-05a-single-digital-life-first-round.md)、式と分類は [Digital Life first-round model v0.1](docs/digital-life-first-round-model_v0.1.md) を参照してください。Stage 4の設計境界は [Garden入力層設計](docs/stage-04-garden-input-layer.md)、モデル値は [Garden input model v0.1](docs/relax-with-light-garden-input-model_v0.1.md)、境界所属の仮定は [RRI window membership policy v0.1](docs/rri-window-membership-policy_v0.1.md) にあります。規範との境界は [規範スコープ](docs/normative-scope.md) を参照してください。

Stage 5Bの設計境界は [3生命・資格競争・第2周](docs/stage-05b-three-life-competition-second-round.md)、配送仮定は [tau touch policy](docs/tau-touch-delivery-policy_v0.1.md) にあります。Stage 5B.1の補正は [出力境界・時刻補正](docs/stage-05b1-output-boundary-timing-correction.md)、Garden規則は [Garden output qualification model v0.2](docs/garden-output-qualification-model_v0.2.md)、発行policyは [qualified B emission policy v0.1](docs/qualified-b-emission-policy_v0.1.md) を参照してください。

Stage 6は [光点滅シミュレーター](docs/stage-06-light-blink-simulator.md)、[B→I mapping](docs/b-to-i-light-mapping-model_v0.1.md)、[Virtual Light Device](docs/virtual-light-device-model_v0.1.md)、[continuous phase policy](docs/continuous-phase-policy_v0.1.md) を参照してください。次工程は **Stage 7: 光に反応する仮想ユーザー** です。Stage 5Cの関係記憶探索も未実装です。
