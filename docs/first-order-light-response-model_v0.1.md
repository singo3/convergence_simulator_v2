# First-order Light Response Model v0.1

## State equation

`first_order_light_response_v0_1` は潜在反応 `R(t)` を0〜1で解析的に評価する。target一定区間では、

```text
R(t) = target + (R_start - target) * exp(-(t - start_time) / tau)
```

を使用する。正式時刻はinteger microsecondsで保持し、指数関数へ渡す直前だけ秒へ変換する。

## Onset / recovery

- `target > R_start`: onset time constant（標準8秒）
- `target < R_start`: recovery time constant（標準12秒）
- `target == R_start`: 定数

target変更時の新segmentは直前segmentの同時刻responseから開始するため、jumpがない。inactive遷移でも即時0へresetしない。

## Target transitions and segments

immutable segmentは半開区間 `[start_time_us, end_time_us)` である。正の長さだけ保存し、gap/overlapを作らない。同一targetの再通知は現在segmentを継続し、target変更時だけ境界を作る。simulation endを超えない。

## Deterministic observation

`response_at(time_us)` は保存済み区間を解析的に評価する。GUI refresh、snapshot頻度、実行速度、step方法に依存しない。100ms診断sampleはrun後に導出し、schedulerへsample eventを追加しない。

## Limitations

一次遅れは最小simulation assumptionであり、遅延、overshoot、habituation、非線形飽和、負反応を表現しない。これらを追加する場合は別versionとする。
