# Stage 01 — 時間シミュレーター設計

## 設計境界

`domain` と `simulation` は純粋なPython coreで、Qtをimportしない。`gui/controller.py` がwall clockとユーザー操作をengine APIへ変換し、widgetsはcontroller snapshotとevent deltaだけを描画する。simulation thread、DB、network、Web serverは導入しない。

## 時刻単位

正式な時刻、duration、event発火時刻は非負のinteger microsecondsで保持する。1秒は1,000,000、2.5秒は2,500,000、7.3秒は7,300,000である。floatは描画用の秒への変換境界でのみ使い、coreで時間を累積しない。変換と `HH:MM:SS.mmm` 表示は `simulation/time_utils.py` に集約する。

## Clock state

`SimulationClock` は `stopped → running ⇄ paused → completed` を基本遷移とする。resetは全stateから開始時刻・stoppedへ戻す。advanceはrunningだけに許可し、時刻後退を拒否し、endでclampする。completed後の進行はresetまで拒否する。speedはClock状態ではない。

## Event schema

`SimulationEvent` はfrozen dataclassで、次を持つ。

- `event_id`: resetで再現する決定論的ID
- `event_type`, `source`
- `scheduled_time_us`
- `priority`
- `sequence`: 登録順の単調増加整数
- `payload`: finiteなJSON値だけを受け入れ、deep-freezeした値

## Event ordering

heap keyは `(scheduled_time_us, priority, sequence)` の昇順である。時刻、priorityが同じでもsequenceで必ず一意に順序が決まる。cancelしたeventはlazy removalされ、pending countと実行列へ入らない。現在時刻より過去およびscenario end後への予約は拒否する。handlerはengine contextを通じて未来eventを追加できる。

handlerが現在時刻へeventを追加する場合、すでに実行中のeventより小さいpriorityを挿入することは拒否し、履歴のordering invariantを守る。

## Step semantics

- `advance_by_us(delta)`: running中だけ、inclusive targetまでの全eventを処理し、targetへclockを合わせる。paused/stopped/completedでは自動進行しない。
- `step_one_second()`: stopped/pausedでも明示的stepとして一時的にrunningへ入り、現在時刻から1,000,000us（end-clamp）までの全eventを実行する。自動実行中でなければstep後はpausedへ戻す。
- `step_one_event()`: next event時刻までclockを進め、正確に1件だけpop・実行する。同時刻eventは次回に残す。
- `run_until_end()`: real-time待機なしで全eventを順に処理する。動的event暴走に備えた件数guardを持つ。

## Speed semanticsとmax mode

QTimerは16ms間隔を目安にcontrollerを起こす。等速・10倍・100倍は `perf_counter_ns()` のmonotonic差分へ整数倍率を掛け、1,000ns単位の剰余を次callbackへ保持してmicrosecondsへ変換する。描画遅延で1 callbackのdeltaが増えても、engineがそのtargetまでのeventを同じqueue順に処理する。

最速と「最後まで実行」はwall-time差分で時刻を作らず、`run_max_batch` を使う。1 callbackは最大500 eventsまたは8msの先着budgetで打ち切り、Qt event loopへ制御を返す。今回の26-event Demoは通常1 batchで完了する。

## Demo scenario

0〜20秒の1秒ごとの21 `clock_tick`、2.5秒と12.75秒のmarker、7.3秒のsame-time A/B、20秒のcompletion、合計26 eventsを予約する。Bを先に登録する一方Aのpriorityを小さくし、実行がA→Bになることを診断する。20秒はtick→completionである。これは時間基盤専用で、実システムモデルではない。

## GUI構成

- status: 仮想時刻、state、速度、next time、pending/executed数
- controls: lifecycle、1秒、1 event、最後まで、4速度
- PyQtGraph timeline: event type別lane、planned marker、current line、incremental executed outline
- QTableView: 実行済みeventだけのappend-only log
- diagnostics: real/virtual elapsed、effective speed、queue、last/next event

planned scatterはload/reset時だけ構築し、通常refreshではcurrent lineを移動し、新規実行点だけをappendする。

## Deterministic digest

実行順ごとに `execution_order`、`event_type`、`scheduled_time_us`、`priority`、`sequence`、`payload` をrecord化する。UTF-8、key sort、空白なし、finite JSONのcanonical表現をSHA-256へ渡す。GUI/headless、速度、reset、描画refresh回数に関係なく同じdigestとなる。

## テスト方針

clock、event、scheduler、engineをunit testし、Demo/headlessをintegration testする。速度は異なるadvance chunkとsnapshot回数で同じdigestになることを確認する。GUIは `QT_QPA_PLATFORM=offscreen` とpytest-qtで生成、全操作、model/timeline更新、completed button state、close時timer停止を実操作する。さらにcore sourceにQt importがないことを検査する。

## 既知の制約

- 単一threadであり、長時間handlerそのものをpreemptしない。batch budgetはevent間で判定する。
- GUI時刻表示はmillisecondsまでだが、coreはmicrosecondsを保持する。
- payloadはJSON互換データだけで、任意Python objectは受け付けない。
- Demoは小規模な診断用で、多数試行、Monte Carlo、性能負荷試験ではない。
- lifecycle stateや実行履歴の永続化、network同期、実デバイス時刻補正は未実装である。
