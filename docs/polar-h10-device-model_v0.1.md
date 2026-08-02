# Ideal Polar H10 RRI device model v0.1

## 位置づけ

- model version: `ideal_polar_h10_rri_device_v0_1`
- RRI event schema version: `rri_measurement_event_v1`

本モデルは、仮想ユーザーの心拍eventからRRIを取得するStage 3のsimulation assumptionである。v2.0が定める「入力デバイスがRRIを出力する」という境界を検証するための理想測定モデルで、実機Polar H10のBLE GATT packet、Heart Rate Service encoding、firmware、電波、pairing、Polar SDKを再現するprotocol emulatorではない。

## Input and output

入力は正式な `HeartbeatEvent` だけである。H10は `event_type=heartbeat`、`source=virtual_user`、`priority=40`、`user_id`、`beat_index`、`scheduled_time_us` を検証し、測定には隣接する `scheduled_time_us` だけを使う。VirtualUserの `HeartbeatRecord`、true RRI、respiratory/slow-wave/correlated/jitter成分を参照しない。

出力は正式な `RriMeasurementEvent` だけである。出力eventは `event_type=rri_measurement`、`source=polar_h10`、`priority=50` で、現在heartbeatと同じ `scheduled_time_us` を持つ。

## RRI measurement

最初のheartbeatではRRIを出力せず、時刻とbeat indexを保持する。2拍目以降のcanonicalな測定値はinteger microsecondsである。

```text
rri_us = current_heartbeat_time_us - previous_heartbeat_time_us
rri_ms = rri_us / 1000
```

`current_heartbeat_time_us` は前時刻より厳密に後で、`rri_us` は正でなければならない。`rri_ms` は表示と後続接続用の導出値である。RRIは再丸め、clip、補間しない。beat indexは前回より大きければよく、連続性は要求しない。

## Event schema and time meaning

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

`RriMeasurementEvent.scheduled_time_us` は、理想H10が現在heartbeatを観測しRRIを出力した仮想時刻で、`current_heartbeat_time_us` と一致する。通信遅延またはセンサ内部clockは表現しない。payloadはimmutableかつJSON serializableで、H10が観測可能な情報だけを持つ。

同一時刻では `(scheduled_time_us, priority, sequence)` により次の順で実行する。

1. `heartbeat` — 40
2. `rri_measurement` — 50
3. `simulation_complete` — 100

## Ideal assumptions

本モデルは次を固定条件とする。

- measurement noise: none
- packet loss: none
- duplicate packet: none
- false beat: none
- missed beat model: none
- quantization: none
- sensor delay: none
- communication delay: none
- artifact insertion: none
- independent random source: none

これらは実機の特性を主張するものではなく、HeartbeatEventからRRI eventへの責務境界を単独検証するための仮定である。

## No filtering or derived physiology

299ms相当の短い正のRRIも2001ms相当の長いRRIもrawのまま出力する。H10は300〜2000ms判定、直近有効RRI中央値との偏差、artifact、confidence、reject、RMSSD、N、Nd、W、baseline、セッション信号Sを計算しない。これらは将来のGarden入力層の責務である。

## Diagnostics and digest

GUI、CSV、headless JSONでVirtualUser内部真値と比較できるが、joinはH10 core外のdiagnostics adapterがcurrent beat indexで行う。各表示は共通のdiagnostic noticeで、誤差が開発用診断であり、H10 event payloadまたはGardenへの正式信号ではないことを明示する。

measurement digestは `measurement_index`、`scheduled_time_us`、device/user ID、previous/current beat index、previous/current heartbeat time、`rri_us`、schema versionをcanonical JSON化したSHA-256である。`scheduled_time_us` は含め、導出値 `rri_ms` とscheduler識別子 `event_id` は除外する。

## Known limitations and future fault models

- 実機のECG電極、beat detection algorithm、RR precisionをモデル化しない。
- BLE packet構造、firmware、電波、pairing、disconnect、reconnectをモデル化しない。
- noise、loss、duplicate、false/missed beat、quantization、latencyをモデル化しない。
- 実機データとの精度比較や校正を行っていない。
- Garden入力層、artifact判定、RMSSD/N変換をモデル化しない。

将来sensor fault modelを追加する場合は、`ideal_polar_h10_rri_device_v0_1` へ暗黙に追加せず、別model version、別Stage、別設定として実装する。
