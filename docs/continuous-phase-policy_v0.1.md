# Continuous phase policy v0.1

`continuous_phase_integrator_v0_1` は、v2.0が明示しないcommand境界の位相を固定するsimulation implementation assumptionである。

このpolicyはVirtual Light Deviceだけが適用する。Garden Light Mapperは位相を積分せず、policy versionと波形parameterを `LightCommandEvent` に明示する。

## Phase equation

phaseはcycle単位の `[0,1)` とし、command開始 `(t0,p0,bpm)` から任意時刻`t`を次で計算する。

```text
phase(t) = fractional_part(p0 + bpm * (t - t0) / 60_000_000)
```

GUI tick数、wall time、描画fps、累積float dtは使用しない。

## Transition rules

- inactive→active: phase 0、Value centerから開始し、`phase_reset=true`。
- active→active: 旧commandの境界phaseを新commandの開始phaseへ継承する。
- same physical command: record/state/segment境界は追加するがphaseは継続する。
- BPM change: cycle位置を継続し、新BPMは境界以後の進行速度だけを変える。
- Hue change: phaseを継続する。
- active→inactive: off、phase null、Value 0。
- inactive→inactive: offを保持する。
- inactive期間後のactive: phase 0から再開始する。

physical equivalenceはactive、Hue、Saturation、Value parameter、BPM、waveform、phase policyだけで判定する。signal index/effective time/holder/event IDとsource BのA/Dは判定へ含めない。

commandは `hold_until_next_command_v0_1` により次commandまで保持する。inactiveは `light_off_black_v0_1` で黒とする。これらのpolicyは光応答生理モデルではなく、Stage 6の再現可能なdevice動作を定める。

`LightStimulusStateEvent` はcommand境界での開始位相を運び、境界間の位相は任意のinteger-microseconds時刻から解析的に導出する。高頻度frame event、GUI tick、`LightStimulusSegment` を正式光時計にしない。segmentは半開区間の監査recordであり、Stage 7の正式入力は `LightStimulusStateEvent` だけである。
