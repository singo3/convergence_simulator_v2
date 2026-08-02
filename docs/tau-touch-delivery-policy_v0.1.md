# tau touch配送policy v0.1

## 位置づけ

規範仕様v2.0は `tau` を0〜1の論理到達時間として定義しますが、仮想時計のmicrosecondsへの写像は定義していません。本書の `tau_to_microsecond_touch_delivery_v0_1` はStage 5Bシミュレーション固有の実装仮定であり、規範式の追加ではありません。

## 写像

1 signalは `1,000,000 us` です。各生命について独立に次を計算します。

```text
touch_offset_us = 1 + floor(clip01(tau) * 999997)
touch_time_us   = signal_time_us + touch_offset_us
```

- `tau=0` は offset `1 us`
- `tau=1` は offset `999,998 us`
- round finalizeは offset `999,999 us`
- 次signalは offset `1,000,000 us`

したがってtouchはsignalより後、finalizeより前、次signalより前に必ず収まります。時刻はinteger microsecondsで保持し、float秒を累積しません。NaN、infinity、boolは拒否します。

## Runtimeの責務境界

Runtimeは各 `DigitalLifeTouchIntent` のtauを個別に上式へ写像し、event queueへ登録するだけです。P/Vを比較せず、tauの最小値探索、順位表、winner選択を行いません。勝者はGardenが実際に配送されたtouch順から決めます。

## 同一microsecondのtie-break

複数touchが写像後に完全に同じ時刻となる場合だけ、`lexicographic_digital_life_id_on_equal_arrival_us` を使用します。RuntimeはintentをID辞書順で登録し、schedulerのsequenceを最終tie-breakにします。異なる到着時刻では時刻が常に優先され、role、P、Vは参照しません。

独立期待値は [stage-05b-reference-vectors.json](conformance/stage-05b-reference-vectors.json) に保存します。
