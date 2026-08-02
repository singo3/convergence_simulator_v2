# Stage 03 — 仮想Polar H10

## 目的

Stage 2の仮想ユーザーが正式出力する `HeartbeatEvent` だけを入力とし、隣接する心拍event時刻の差からraw RRIを測定する。測定値は `RriMeasurementEvent` として同じ決定論的仮想時間上へ出力し、将来のGarden入力層と接続できる境界を作る。

正式信号経路は次のとおりである。

```text
仮想ユーザー
  → HeartbeatEvent
  → 仮想Polar H10
  → RriMeasurementEvent
  → 将来のGarden入力層
```

## 規範と入力デバイス責務

v2.0上、入力デバイスであるPolar H10の正式出力はRRIである。Stage 3はこの入力デバイス境界を実装する。正確な観測、欠損なし、誤差なし、遅延なしとする `ideal_polar_h10_rri_device_v0_1` の具体設計はv2.0規範ではなく、Stage 3のsimulation assumptionである。

H10はRMSSD、N、N_baseline_session、Nd、W、artifact、evaluation quality、baseline、bundle評価、セッション信号Sを計算しない。RRIの絶対範囲判定、300ms未満の `too_short`、2000ms超の `too_long`、中央値偏差、artifact率、RMSSD、N変換は将来のGarden入力層の責務である。正のRRIは短くても長くてもclip、除外、補間、修正せずrawのまま出力する。Garden入力層はStage 3では未実装である。

## Fixed versions and regression baselines

- project version: `0.3.0`
- virtual user model: `baseline_virtual_user_physiology_v0_1`
- Polar H10 model: `ideal_polar_h10_rri_device_v0_1`
- RRI event schema: `rri_measurement_event_v1`
- `document_version`: `v2.0`
- `profile_version`: `symbiotic_signal_loop_reference_v1_0`
- `algorithm_version`: `adaptive_random_search_confirmed_v1`
- `state_schema_version`: `relation_memory_state_v2`

Stage 3開始時に固定した回帰digestは次のとおりである。

- Stage 1 deterministic digest: `1c4217065fa29316e7ead83c4d604e87f9fe8fe46e82b689b5566dbc9890598d`
- Stage 2 heartbeat digest: `4c039f5f1b5cc3cd78682cca890a8a6ec70510a52b4ad4addeabcb0ecd3ae765`
- Stage 2 diagnostic digest: `ef0bc8c644e8b5f6fc2c3b58ef825491e49e005bc0c6c22a9f0c62c66168cd8f`
- Stage 2 full event digest: `761a2dc6b2b03c4d538a85d95160f2ecc731e301a1362006ee97ea575872bddb`

Stage 3検証環境はPython 3.13.4、PySide6 6.11.1、PyQtGraph 0.14.0、NumPy 2.5.1、pytest 9.1.1、pytest-qt 4.5.0、Ruff 0.16.1である。

## HeartbeatEvent input

H10 coreは `event_type=heartbeat`、`source=virtual_user`、`priority=40`、payloadが `user_id` と `beat_index` だけのeventを受理する。`user_id` はdevice configの `expected_user_id` と一致し、`beat_index` はboolでない0以上のintegerで、2拍目以降は前回より大きいことを要求する。beat indexの連続性は要求しない。

正式測定入力は `SimulationEvent.scheduled_time_us` である。`HeartbeatRecord`、内部真値RRI、生理モデルの内部stateを参照しない。不正eventは黙って無視せず拒否する。

## RriMeasurementEvent schema

- `event_type`: `rri_measurement`
- `source`: `polar_h10`
- `priority`: `50`
- `scheduled_time_us`: 現在heartbeatの `scheduled_time_us`

```json
{
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
```

`rri_us` はcanonicalな測定値で、`rri_ms` は `rri_us / 1000` の導出値である。payloadはJSON serializableかつimmutableで、true RRI、RMSSD、N/Nd/W、artifact、生理モデル内部成分を含めない。

## Event ordering and RRI calculation

同一仮想時刻のevent順序はpriorityにより次に固定する。

1. `heartbeat` — priority 40
2. `rri_measurement` — priority 50
3. `simulation_complete` — priority 100

最初のheartbeatでは前心拍がないためRRIを出力せず、時刻とbeat indexを保持する。2拍目以降は次を計算し、現在heartbeatと同じ仮想時刻へ `RriMeasurementEvent` を予約する。

```text
rri_us = current_heartbeat_time_us - previous_heartbeat_time_us
rri_ms = rri_us / 1000
```

時刻は前回より厳密に後、`rri_us` は正でなければならない。scenario終了時刻とheartbeatが一致する場合も、heartbeat、RRI measurement、completionの順で実行する。

## Component lifecycle, reset, and integrated factory

`PolarH10Component` はimmutable config、`ready / measuring / completed` state、観測heartbeat数、前時刻・前beat index、immutable measurement records、snapshot、measurement digestを持つ。BLE接続処理はなく、scenario開始時から測定可能である。completion handlerは同時刻のRRI出力後にstateを `completed` へ変える。

`create_polar_h10_simulation(...)` はVirtualUser、Polar H10、scenario、engineを構築し、heartbeat handlerとcompletion handlerを1回だけ登録する。GUIとheadlessはこのfactoryを共有する。scenarioの `schedule()` はVirtualUserとH10の両方をresetし、初期eventを再構築するため、event ID、sequence、record、measurement index、digestを再現できる。Stage 2の `create_virtual_user_simulation(...)` は独立したまま維持する。

## GUI and diagnostics separation

既定GUIの主対象はStage 3で、中央に次の3 tabを持つ。

1. 仮想ユーザー
2. Polar H10
3. 時間・イベント診断

Polar H10 tabはideal modeの固定条件、状態、RRI比較graph、誤差graph、最近の測定tableを表示する。H10 coreはVirtualUser recordをjoinせず、GUIまたは独立diagnostics adapterだけがcurrent beat indexで `HeartbeatRecord` と `RriMeasurementRecord` を比較する。理想モデルの期待絶対誤差は0usである。この比較は開発用診断であり、Gardenへ渡す正式信号は `RriMeasurementEvent` だけである。

## Headless and CSV

Stage 3標準180秒scenarioはreal-time待機なしで実行できる。

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-h10-demo
```

JSONはproject/model/schema version、config、実行統計、heartbeat/RRI数、raw RRI統計、開発用一致比較、heartbeat/measurement/full-event digestを分離する。`diagnostic_notice` で真値比較が開発用診断であり、正式信号は `RriMeasurementEvent` だけであることを明示する。RMSSD、N、Nd、W、artifact評価はStage 3 JSONへ含めない。

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-h10-demo --export-h10-csv polar_h10_rri_measurement_diagnostics.csv
```

CSVのdevice output列はH10のraw測定、`diagnostic_*`、`absolute_error_us`、`match` 列は開発用比較である。`diagnostic_notice` 列で「仮想ユーザー内部真値との比較は理想H10を確認する開発用診断であり、Gardenへ渡す正式信号はRriMeasurementEventだけ」と明示する。GardenはCSVを読まず、将来 `RriMeasurementEvent` を直接受信する。CSV exportの有無はsimulation結果とdigestを変えない。

## Measurement digest

`rri_measurement_digest` は各measurementの次のfieldを配列順に並べ、key sort、UTF-8、compact separators、finite JSONでcanonical JSON化したSHA-256である。

- `measurement_index`
- `scheduled_time_us`
- `device_id`
- `user_id`
- `previous_beat_index`
- `current_beat_index`
- `previous_heartbeat_time_us`
- `current_heartbeat_time_us`
- `rri_us`
- `event_schema_version`

`scheduled_time_us` は正式出力時刻としてdigestに含める。`rri_ms` は `rri_us` から導出可能で、`event_id` はschedulerの識別子であるため、どちらもmeasurement digestから除外する。

## Tests and determinism

config/schema validation、不正heartbeat拒否、1拍目非出力、手計算RRI、rawな299/300/2000/2001ms、event ordering、immutable payload/record/snapshot、reset、handler重複防止、180秒integration、開発用真値一致、headless/CSV/GUI、Qt/VirtualUser内部/Garden/RMSSD/randomへの非依存を検証する。

`run_until_end`、1秒step、1event step、等速/10倍/100倍相当のadvance、max batch、reset、snapshot回数、chart表示、CSV export、H10 config JSON round-tripの違いでheartbeat列とRRI measurement digestが変わらないことを回帰検証する。

## 次Stageとの接続点

次工程のGarden入力層は `RriMeasurementEvent` を直接受信し、RRI範囲、中央値偏差、artifact率、confidence、evaluation reject、RMSSD、N、baseline、セッション時間構造を担う。Stage 3はそれらを先回り実装しない。
