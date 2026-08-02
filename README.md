# 環境共生型デジタル生命シミュレーター v2

環境共生型デジタル生命システムの各componentを、同じ決定論的な仮想時間上で段階的に検証するPythonプロジェクトです。

- Stage 1「時間・イベント配送基盤」: 完成
- Stage 2「外部刺激を受けない仮想ユーザー」: 完成
- Stage 3「仮想Polar H10」: 完成
- 現在のGUI主対象: Stage 3 仮想Polar H10

正式な信号経路は次のとおりです。

```text
仮想ユーザー
  → HeartbeatEvent
  → 仮想Polar H10
  → RriMeasurementEvent
  → 将来のGarden入力層
```

仮想ユーザーの正式出力は `HeartbeatEvent` だけです。仮想Polar H10は隣接するheartbeatの正式時刻差をraw RRIとして測定し、`RriMeasurementEvent` だけを正式出力します。H10はRMSSD、N、Nd、W、artifact判定を行いません。RRI範囲判定やRMSSD/N変換を担うGarden入力層はまだ実装していません。

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

## Requirements / setup

- Python 3.12以上
- PySide6 / Qt Widgets
- PyQtGraph / NumPy
- pytest / pytest-qt
- Ruff

Stage 3固定検証環境はPython 3.13.4、PySide6 6.11.1、PyQtGraph 0.14.0、NumPy 2.5.1、pytest 9.1.1、pytest-qt 4.5.0、Ruff 0.16.1です。

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

GUI上部にはStage 1共通の時計、状態、速度、step controlsがあります。中央のtabは次の3つです。

1. 仮想ユーザー: Stage 2設定、内部真値の開発用診断
2. Polar H10: ideal mode固定条件、raw RRI、真値比較、誤差、測定table
3. 時間・イベント診断: timeline、実行済みevent log、wall/virtual time診断

仮想ユーザー設定は開始前またはreset後だけ変更できます。H10にはnoise、latency、packet loss、artifact rateなどの調整parameterはありません。

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

いずれもreal-time待機をせずJSONを標準出力します。既存Stage 2 JSONは変更せず、Stage 3 JSONはraw RRI統計、一致比較、heartbeat/measurement/full-event digestを分離します。Stage 3 JSONへRMSSD、N、Nd、W、artifact評価を含めません。

## 開発用CSV export

Stage 2の仮想ユーザー内部真値:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-virtual-user-demo --export-virtual-user-csv virtual_user_true_heartbeat_diagnostics.csv
```

Stage 3のH10 raw測定と独立診断比較:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-h10-demo --export-h10-csv polar_h10_rri_measurement_diagnostics.csv
```

GUIからも両診断CSVを保存できます。H10 CSVのraw device output列と `diagnostic_true_rri_*` / `absolute_error_us` / `match` 列は責務上分離され、`diagnostic_notice` 列で開発用比較であることを明示します。将来のGardenはCSVではなく `RriMeasurementEvent` を直接受信します。Stage 3 headless JSONも同じ `diagnostic_notice` を持ち、exportの有無はsimulation結果とdigestを変えません。

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

## Deterministic digest baselines

- Stage 1: `1c4217065fa29316e7ead83c4d604e87f9fe8fe46e82b689b5566dbc9890598d`
- Stage 2 heartbeat: `4c039f5f1b5cc3cd78682cca890a8a6ec70510a52b4ad4addeabcb0ecd3ae765`
- Stage 2 diagnostic: `ef0bc8c644e8b5f6fc2c3b58ef825491e49e005bc0c6c22a9f0c62c66168cd8f`
- Stage 2 full event: `761a2dc6b2b03c4d538a85d95160f2ecc731e301a1362006ee97ea575872bddb`

Stage 3 measurement digestは `scheduled_time_us` とcanonicalな `rri_us` を含み、導出可能な `rri_ms` とscheduler識別子 `event_id` を除外します。

## Test / lint / smoke

```bash
.venv/bin/python -m compileall -q src tests
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q
.venv/bin/ruff check .
QT_QPA_PLATFORM=offscreen .venv/bin/python -m symbiotic_sim_v2 --smoke-test --auto-close-ms 2500
```

テストはStage 1・2全回帰に加え、H10 config/event validation、first heartbeat、手計算RRI、raw RRI保持、同時刻ordering、reset、速度・step・描画・CSV非依存のdigest、headless、offscreen GUI、architecture分離を確認します。

設計境界は [Stage 3設計](docs/stage-03-virtual-polar-h10.md)、H10仮定は [理想H10 device model v0.1](docs/polar-h10-device-model_v0.1.md)、Stage 2生理式は [仮想ユーザー生理モデルv0.1](docs/virtual-user-physiology-model_v0.1.md)、規範との境界は [規範スコープ](docs/normative-scope.md) を参照してください。

次工程は **Garden入力層とセッションシグナル** です。RRI範囲・中央値判定、artifact、RMSSD、N、baseline、セッション時間構造はStage 3へ先回り実装していません。
