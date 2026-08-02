# B→I light mapping model v0.1

## Version

- Mapper model: `relax_with_light_b_to_i_mapper_v0_1`
- Mapping: `relax_with_light_pc_hsv_sine_mapping_v0_1`
- input: `garden_qualified_b_event_v2`
- output: `light_command_event_v1`

## 規範写像

v2.0 Relax with Light参照値に従い、activeな資格holderの `B=[F,A,T,D]` を次へ写像する。

```text
Hue_degree = 360 F
blink_BPM = 10 + 155 T
Saturation = 1.0
Value(phase) = 0.425 + 0.075 sin(2π phase)
Value_min = 0.35
Value_max = 0.50
waveform = sine
```

F/Tを0〜1でstrict validationし、範囲外値をclipしない。A/Dも正式Bとして0〜1を検証・record化するが、Hue、BPM、Saturation、Value parameterへ影響させない。

## Stage 6 representation assumption

F=1ではformal Hue=360.0を保持する。`render_hue_degree = hue_degree mod 360` はGUI rendering用の別fieldであり、v2.0のformal Hueを0.0へ書き換える式ではない。render Hue、strict event validation、priority 66、`light_command_event_v1` の具体payloadと1入力1commandの配送規則は、規範写像を決定論的に検証するStage 6実装仕様である。

inactiveはHue/render Hue/BPM/source B/holderをnull、Saturationと全Value parameterを0、waveform=`off`とする。

## Configと境界

`GardenLightMapperConfig` はimmutableで、version、360 scale、10〜165 BPM、Saturation、Value center/amplitude/min/max、F/T使用・A/D不使用、phase/hold/inactive policyを固定する。unknown/missing field、bool-as-number、NaN/Infinity、version不一致を拒否する。

固定policyは `continuous_phase_integrator_v0_1`、`hold_until_next_command_v0_1`、`light_off_black_v0_1` である。Mapper自身はphaseを積分せず、これらを後続Deviceとのcommand contractへ明示する。

Mapperの正式入力は `GardenQualifiedBEvent v2` のみであり、Digital Life、Garden output component/record、P/V/tau、W/E/q/k/G、RRI/RMSSD/Nを参照しない。1入力につき同じeffective microsecondへpriority 66の `LightCommandEvent` を1件生成する。

## 限界

これは論理的なHSV刺激であり、sRGB pixel、モニターgamma、cd/m²、色度、分光分布、周囲照明、視距離、実LED機器を校正または再現しない。VirtualUserの光応答とStage 5Cの関係記憶探索もこのMapperの範囲外である。
