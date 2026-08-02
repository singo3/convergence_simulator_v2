# Stage 5B.1 Garden出力境界・実効時刻補正

## 目的

Stage 5Bではactiveなqualified Bを1秒roundのfinalize時刻に発行していた。この時刻をそのままStage 6の適用開始にすると、holder生命がcurrent signalで生成したBの利用がsignal末尾まで遅れる。Stage 5B.1は、Bの生成元とformal出力の因果を同じsignal内で明確にする限定補正である。

旧経路は `holder touch → round finalize → qualified B → feedback → 第2周`、新経路は `holder touch → qualified B → 残りtouch → round finalize → feedback → 第2周` である。標準fixtureの最初のactive signalでは、旧eventは `60,999,999 us`、holder touchは `60,551,540 us` だった。新eventのeffective timeは `60,551,540 us` になる。

## Formal touch boundary

`digital_life_touch_event_v2` のpayloadは次のfieldだけを持つ。

- `digital_life_id`
- `signal_index`
- `signal_time_us`
- `b_f`, `b_a`, `b_t`, `b_d`
- `schema_version`

role、P、V、tau、touch offset、N/Nd/W、E/q/k/Gは含まない。roleはDigital Life configに残るRuntime/GUI診断情報であり、Gardenのformal recordにも保存しない。parserはexact field setとv2だけを受理し、v1やunknown fieldへfallbackしない。

## Runtime roster

参加する3つの`digital_life_id`はRuntime/session rosterからGarden configへ注入する。Gardenは各IDを非空・一意として検証し、lexical tie-breakに使える順序へ正規化するが、`life-red`、`life-green`、`life-blue`やrole対応をcore規則として固定しない。標準3生命は再現用fixtureである。

## Active emission

`qualified_b_on_holder_touch_v0_1`では、holder未割当なら最初のactual touchがholderを確定し、そのtouchのBを同じ到着microsecondへpriority 65で発行する。既にholderがあるroundでは、先に来たnon-holder touchは出力せず、holder自身のtouchが到着したときだけcurrent signalのBを発行する。

`garden_qualified_b_event_v2` は `effective_time_us` とpolicy versionを明示する。active時は次を同時に満たす。

```text
signal_time_us < effective_time_us < signal_time_us + 1_000_000
event.scheduled_time_us = effective_time_us = holder touch arrival_time_us
active = true
qualification_holder_id != null
B != null
```

1 active signalにつき1件だけであり、round finalizeは再発行しない。

## Inactive emission and closing

S=0ではtouchを発行せず、no-touch finalize priority 31が同じsignal timeへinactive qualified B priority 65とfeedback priority 80を予約する。inactive eventは `effective_time_us = signal_time_us`、holder null、B nullである。

240秒closingもinactive commandを240秒ちょうどに出す。feedbackはrelease前holderと各生命のlast active Bを保持し、Bundle 2評価を全3生命の第2周へ帰属する。その後だけholder release priority 90、simulation complete priority 100へ進む。

## Event ordering

active roundの順序は次のとおりである。

```text
signal                 priority 30
DigitalLifeTouchEvent  priority 60
GardenQualifiedBEvent  priority 65 (holder touchと同時刻)
round finalize         priority 70 (signal + 999,999 us)
feedback               priority 80
```

同一microsecondのtouchはすべてpriority 60で処理し、既存scheduler registration sequenceによるlexical ID順を維持する。qualified B priority 65は同時刻の全touch後に動作してよいが、Bは実際に割り当てられたholderのtouch値である。

## Round finalize responsibility

active finalizeは3touchとexpected rosterの一致、holder touchの存在、active outputが既にちょうど1件であること、ID/B/effective timeがholder touchと一致することを検証する。その後にtouch/qualification recordを確定し、各生命自身のBを含むfeedbackを3件発行して第2周を同期する。未発行、重複、不一致はsilent fallbackせずincomplete round errorとする。

## Semantic regression

この補正はtouch scheduled time/order、holder assignment/hold/release、G、E、q、固定k、feedback time、第2周time、closing帰属を変更しない。変更対象はproject/model/schema/policy version、formal touch payload、qualified B effective time、関連record/CSV/digestだけである。Stage 1〜5Aのevent、JSON、digest、CSVは不変とする。

## Stage 6 interface

Stage 6の唯一の正式入力は`garden_qualified_b_event_v2`である。consumerは受信時刻からBを適用し、次commandまで保持できる。active commandはcurrent signalのholder touch時刻、inactive commandはsignal時刻に届くため、round finalize由来の約1 signal遅延を作らない。Stage 5B.1はHue、BPM、光波形I、光に対するVirtualUser応答を実装しない。
