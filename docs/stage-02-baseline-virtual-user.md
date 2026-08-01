# Stage 02 — 外部刺激なしbaseline virtual user

## 目的

Stage 1のinteger-microseconds時計とdeterministic event scheduler上で、外部刺激がなくても内部由来の変動を持つheartbeat列を生成する。標準scenarioは180秒で、model versionは `baseline_virtual_user_physiology_v0_1` である。

このモデルは実データで未校正のsimulation assumptionであり、実在する人の生理を証明せず、医療用途を意図しない。

## 責務境界

VirtualUserComponentの正式出力は `HeartbeatEvent` だけである。RRI、HRV、RMSSD、artifact、H10測定値、Garden入力、N/Nd/W、光への評価を出力しない。内部の `HeartbeatRecord` はGUI、test、CSVの開発診断にだけ使用し、後続componentへ配送しない。

仮想H10は次Stage以降にheartbeat timestamp差からRRIを測定する。Stage 2はH10、Garden、セッションシグナル、光刺激を実装しない。

## HeartbeatEvent schema

- `event_type`: `heartbeat`
- `source`: `virtual_user`
- `priority`: `40`
- 正式時刻: `SimulationEvent.scheduled_time_us`
- payload: `{"user_id": string, "beat_index": integer}` の2 fieldだけ

最初のheartbeatは0us、beat index 0である。前heartbeatがないため最初のrecordにはRRIがない。simulation endと一致するheartbeatは許可し、priority 40によりpriority 100のcompletionより先に実行する。

## Component lifecycle

1. `reset()` がrecords、前時刻、AR(1)状態、pending intervalを初期化する。
2. `schedule_initial()` がheartbeat 0を予約する。
3. engineがheartbeatを正式時刻でhandlerへ配送する。
4. componentが直前に計算済みのintervalとtimestamp差を診断recordへ保存する。
5. 現在heartbeat時刻・beat index・AR(1)状態から次intervalを計算する。
6. next timeがscenario end以下の場合だけ未来heartbeatを予約する。

snapshotとrecordsはimmutable object/tupleとして返す。heartbeat digestは `beat_index` と `heartbeat_time_us` だけをcanonical JSON化したSHA-256である。内部component値のdiagnostic digestは別にする。

## Scenario lifecycleとreset

`create_virtual_user_simulation(config)` はcomponent、scenario、engineを生成し、heartbeat handlerを1回だけ登録してscenarioをloadする。GUIとheadlessは同じfactoryを使用する。

`VirtualUserScenario.schedule()` はcomponentをresetし、initial heartbeatとcompletionを再構築する。Stage 1 engine resetが同じscenario scheduleを呼ぶため、event IDs、sequences、records、heartbeat digestを完全再現する。

## Deterministic random

`root_seed:stream_name:sample_index` をUTF-8 encodingしSHA-256へ渡す。64-bit chunkへ0.5を加えてopen interval `(0,1)` のuniformを作り、2 chunkのBox-Mullerでstandard normalを得る。

streamは `correlated_innovation` と `beat_jitter` を分ける。global RNG、Python `hash()`、呼出順、GUI refresh、速度へ依存しない。

## GUI

共通上部に時計、state、queue、lifecycle/step、4速度を置く。中央は次の2 tabである。

1. 仮想ユーザー: pre-run config、主要状態card、heartbeat/RRI/HR/RMSSD/component chart、最近のheartbeat table
2. 時間・イベント診断: Stage 1 timeline、実行済みevent log、wall/virtual time診断

設定はstopped状態だけ編集できる。適用時は共通factoryでscenarioを再構築し、engine、records、charts、tables、event logを初期化する。PlotDataItemは保持し、`setData`で更新する。

## Developer diagnostics

- 真のRRI: heartbeat timestamp差
- 瞬時HR: `60000 / true_rri_ms`
- rolling RMSSD: 現在時刻から直近30秒内に終了した全true RRI
- full-run RMSSD: 全true RRI
- 内部成分: respiratory、slow wave、correlated、jitter、合成後RRI

artifact除外、H10誤差、N/W変換は行わない。RRIが2個未満のRMSSDはundefinedとしてGUI plotから除外する。

## Tests

Stage 1全回帰に加え、configの全range、canonical random reference、数式component、clamp/rounding、手計算RRI/RMSSD、30秒window、payload境界、end同時刻、reset、seed、step/chunk/max、headless/GUI digest、CSV非干渉、Qt/H10/Garden非依存を検証する。

## 次Stageとの接続点

次工程のセッションシグナルシミュレーターは同じSimulationEngine上へ独立eventを追加できる。将来の仮想Polar H10は `heartbeat` eventの `scheduled_time_us` だけを測定入力として受け、Stage 2のHeartbeatRecordを直接参照しない。
