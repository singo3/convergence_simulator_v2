# qualified B emission policy v0.1

## Status

`qualified_b_on_holder_touch_v0_1`は、v2.0規範が固定していないmicrosecond-level発行時刻を定めるsimulation implementation assumptionである。Gardenの資格規則やDigital Lifeの演算式を変更しない。

## Active signal

holderが未割当なら最初にactual arrivalしたtouchでholderを確定し、そのtouch Bを同じ時刻に発行する。holderが既にいる場合は、そのIDのtouchが到着するまで発行せず、current signalのholder Bを同じ時刻に発行する。non-holderが先着しても代用しない。active signalごとにちょうど1 eventである。

```text
effective_time_us = holder_touch.arrival_time_us
GardenQualifiedBEvent.scheduled_time_us = effective_time_us
priority = 65
```

round finalizeは発行済みeventを検証するだけで、同じBを再送しない。feedbackと第2周は従来のfinalize後に維持する。

## Exact tie

同じarrival microsecondのtouchはpriority 60と既存のregistration sequenceで処理する。session rosterはlexical orderへ正規化されるため、equal timeの決定順は再現可能である。最初に配送されたIDがholderになり、そのholder touch Bをtie timeへpriority 65で発行する。同時刻の全priority 60 touchが先に処理されても、holder/Bは変わらない。

## Inactive signal

S=0ではtouchがなく、inactive commandをsignal timeへ発行する。

```text
effective_time_us = signal_time_us
active = false
qualification_holder_id = null
B = null
```

240秒closingも同じinactive commandである。closing feedbackのholder/B帰属と、その後のreleaseは別責務として維持する。

## Stage 6 hold-until-next-command contract

Stage 6は`garden_qualified_b_event_v2`を受信した時点からcommandを適用し、次のqualified B eventまで保持できる。active commandがholder touch時刻に届くため同一signal内の介入が可能で、signal末尾finalize由来の遅延を持ち込まない。inactive commandはbaselineまたはclosingのsignal timeに届く。

Stage 5B.1はconsumer自体、Hue/BPM mapping、光波形I、VirtualUserの光応答を実装しない。
