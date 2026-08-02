# Stationary Light Preference Model v0.1

## Scope

`stationary_hue_bpm_gaussian_preference_v0_1` は、1 run中に変化しないHue/BPM反応特性を定義するsimulation assumptionである。学習、順応、嫌悪、関係記憶は扱わない。

## Circular Hue distance

```text
raw = abs(render_hue_degree - preferred_hue_degree)
hue_distance = min(raw, 360 - raw)
```

このため0°と360°は同一点で、359°と1°の距離は2°である。

## Gaussian matches

```text
hue_match = exp(-0.5 * (hue_distance / hue_sigma_degree)^2)
bpm_match = exp(-0.5 * ((blink_bpm - preferred_blink_bpm) / blink_sigma_bpm)^2)
preference_match = hue_match * bpm_match
```

値域は0〜1で、中心では1になる。inactiveではHue/BPM matchを未定義、総合matchを0とする。

## Fixed inputs

関数へ渡すのは物理projectionと固定設定だけである。時刻、session/bundle、holder ID、source B、source signal、Saturation、瞬時Value、phase、N、Wを使用しない。provenanceは監査receiptだけに残す。

## Non-negative effect

好みに合う光は正のtarget、合わない光は0に近いtarget、inactiveは0となる。負の反応や嫌悪は別model versionが必要である。

## Limitations

パラメータは実測から推定しておらず、run間の個人差を表す診断presetである。moving preference、疲労、履歴依存、Saturation/Value依存はStage 7に含めない。
