# 環境共生型デジタル生命シミュレーター v2

環境共生型デジタル生命システムの各componentを、同じ決定論的な仮想時間上で段階的に検証するPythonプロジェクトです。

- Stage 1「時間・イベント配送基盤」: 完成
- Stage 2「外部刺激を受けない仮想ユーザー」: 完成
- 現在のGUI主対象: Stage 2仮想ユーザー

Stage 2で仮想ユーザーが正式に出力するのは、指定仮想時刻に1拍発生したことを表す `HeartbeatEvent` だけです。画面やCSVに表示する真のRRI、瞬時心拍数、rolling/full-run RMSSD、内部変動成分は開発用診断であり、仮想Polar H10の測定値でもGarden入力信号でもありません。

生理モデル `baseline_virtual_user_physiology_v0_1` は、呼吸性変動、slow wave、AR(1)連続変動、拍ごとのjitterを明示的に組み合わせたsimulation assumptionです。実データで未校正であり、実在する人の生理を証明するモデル、医療用途のモデルではありません。

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
- SHA-256/Box-Mullerによるstateless named random source
- 外部入力を参照しないbaseline physiology
- payloadを `user_id` / `beat_index` だけに限定したheartbeat event
- reset・速度・描画回数に依存しないheartbeat列
- 真のRRI、瞬時HR、rolling RMSSD 30秒、full-run RMSSDの開発用診断
- PyQtGraph charts、最近の心拍table、設定panel、Stage 1時間診断tab
- headless JSONと診断CSV export

仮想Polar H10、Garden入力層、N/Nd/W、セッションシグナルS、光刺激はまだ実装していません。

## Requirements / setup

- Python 3.12以上（開発環境は3.13）
- PySide6 / Qt Widgets
- PyQtGraph / NumPy
- pytest / pytest-qt
- Ruff

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

macOSでは、汎用launcher `環境共生型デジタル生命シミュレーターv2を起動.command` をダブルクリックできます。Stage 1で作成した `時間シミュレーターを起動.command` も後方互換用に残しており、現在は同じStage 2 GUIを開きます。

GUI上部にはStage 1共通の時計・速度・step controlsがあります。仮想ユーザーtabでは開始前またはreset後にconfigを変更できます。running、paused、completed中は設定を変更できません。時間・イベント診断tabでは、Stage 1のtimeline、event log、wall/virtual time診断を現在のVirtualUserScenarioに対して表示します。

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

どちらもreal-time待機をせずJSONを標準出力します。Stage 1 digestはStage 2追加前と同じです。Stage 2 JSONはconfig、beat統計、RMSSD、heartbeat digest、full event digestを分離して出力します。

## 開発用CSV export

```bash
.venv/bin/python -m symbiotic_sim_v2 \
  --headless-virtual-user-demo \
  --export-virtual-user-csv virtual_user_true_heartbeat_diagnostics.csv
```

GUIの「診断CSVを保存」でも出力できます。ファイルは内部真値の開発診断であり、H10測定データではありません。CSVの有無はheartbeat生成結果へ影響しません。

## HeartbeatEvent境界

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

正式な心拍時刻は `SimulationEvent.scheduled_time_us` です。RRI、RMSSD、N、Nd、W、内部noiseをpayloadへ入れません。将来の仮想H10はheartbeat時刻差からRRIを測定します。

## Test / lint / smoke

```bash
.venv/bin/python -m compileall -q src tests
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q
.venv/bin/ruff check .
QT_QPA_PLATFORM=offscreen .venv/bin/python -m symbiotic_sim_v2 \
  --smoke-test --auto-close-ms 2000
```

テストはStage 1回帰に加え、config validation、canonical random values、数式component、手計算RMSSD、event boundary、reset/速度/step/GUI描画の決定性、CSV、offscreen GUI、architecture分離を確認します。

設計境界は [Stage 2設計](docs/stage-02-baseline-virtual-user.md)、モデル数式は [生理モデルv0.1](docs/virtual-user-physiology-model_v0.1.md)、規範との境界は [規範スコープ](docs/normative-scope.md) を参照してください。

次工程は **セッションシグナルシミュレーター** です。本Stageでは先回りして実装していません。
