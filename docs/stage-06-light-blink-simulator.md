# Stage 6 Garden Light Mapper・仮想光点滅デバイス

## 目的とsystem boundary

Stage 6は、Stage 5B.1の正式出力 `garden_qualified_b_event_v2` だけを入力として、資格生命の抽象出力 `B=[F,A,T,D]` を論理的なHSV光刺激 `I` へ変換する。正式経路は次で閉じる。

```text
GardenQualifiedBEvent v2 (priority 65)
  -> Garden Light Mapper
  -> LightCommandEvent = I (priority 66)
  -> Virtual PC Light Device
  -> LightStimulusStateEvent (priority 67)
  -> 将来のStage 7 VirtualUser
```

MapperとDeviceはGUI非依存である。MapperはB→Iの規範写像、Deviceはcommand保持、連続位相、任意時刻state、刺激segmentを担当する。QTimer、QColor、描画fpsは正式信号や位相へ使わない。

## Version contract

| 区分 | version |
| --- | --- |
| project | `0.7.0` |
| Mapper model | `relax_with_light_b_to_i_mapper_v0_1` |
| B→I mapping | `relax_with_light_pc_hsv_sine_mapping_v0_1` |
| Light command schema | `light_command_event_v1` |
| Device model | `virtual_pc_light_device_v0_1` |
| Stimulus state schema | `light_stimulus_state_event_v1` |
| Segment schema | `light_stimulus_segment_v1` |
| Phase policy | `continuous_phase_integrator_v0_1` |
| Hold policy | `hold_until_next_command_v0_1` |
| Inactive policy | `light_off_black_v0_1` |
| Waveform sample policy | `fixed_virtual_grid_20ms_v0_1` |

規範仕様のversion tupleは `v2.0` / `symbiotic_signal_loop_reference_v1_0` / `adaptive_random_search_confirmed_v1` / `relation_memory_state_v2` のまま変更しない。

## 規範値とsimulation implementation assumption

v2.0のRelax with Light参照仕様から採用する規範範囲は、`I=M_garden(B_qualified_holder)`、`B=[F,A,T,D]`、Hue、blink BPM、Saturation、Value範囲、sine波、およびPC出力でA/Dを使用しないことである。

一方、`render_hue_degree = hue_degree mod 360`、位相0の開始点、active command間の位相継続、command hold、inactive black、priority 66/67、event/schemaの具体形、segment、20ms sampling、GUI previewはStage 6でversion管理する **simulation implementation assumptionまたは開発用診断** である。これらをv2.0本文が定めた値として扱わない。

## B→I

active commandでは `Hue_degree=360F`、`blink_BPM=10+155T`、Saturation=1.0、Value=`0.425+0.075 sin(2πphase)` とする。したがってValue範囲は0.35〜0.50である。A/Dはsource Bとして監査recordへ残すが、PC光parameterへ使用しない。F=1のformal Hueは360.0を保持し、GUI描画だけ0.0へmoduloする。

inactive commandはholder/B/Hue/BPMをnull、Saturation/Value parameterを0、waveformを`off`とし、黒として扱う。

## command holdとcontinuous phase

commandは次commandのeffective timeまで半開区間で保持する。inactive→activeだけphaseを0へresetする。active→activeは旧commandを新effective timeまで解析的に進めたphaseを新commandの開始phaseとする。同じB、Hue変更、BPM変更、holder/source metadata変更でもphaseをresetしない。active→inactiveはoff、inactive期間後のactiveは0から再開する。

位相はinteger-microsecondsの仮想時刻から解析的に求める。frameごとのfloat dt累積や60Hz frame eventは作らない。

## state queryとsegment

`VirtualLightDeviceComponent.state_at(time_us)` はcommand履歴から過去を含む任意の0〜240秒時刻を決定論的に再構成する。240秒を超えるqueryはsilent clampせず拒否する。

各commandは `[start_time_us,end_time_us)` の `light_stimulus_segment_v1` を開始し、次commandで前segmentを閉じる。正時間segmentだけを保存し、gap/overlapを許さない。標準241 commandでは、240秒ちょうどのclosing commandがzero-durationになるため240 segmentを保存する。

`LightStimulusSegment` は監査recordであり、Stage 7へ配送するformal eventではない。Stage 7へ渡す正式境界は、各commandと同じeffective timeに1件だけ生成する `LightStimulusStateEvent` である。

## event ordering

active signalはtouch 60 → qualified B 65 → LightCommand 66 → LightStimulusState 67 → round finalize 70 → feedback 80である。inactiveはno-touch finalize 31 → 65 → 66 → 67 → feedback 80、closingは評価25 → signal30 → finalize31 → 65 → 66 → 67 → feedback80 → release90 → complete100となる。Stage 6はfeedback、第2周、releaseの時刻を変更しない。

## GUI・headless・CSV

7タブGUIの先頭に光点滅tabを追加し、現在state、色preview、直近波形、全session parameter、command表、segment表を表示する。実点滅previewは明示opt-inで初期OFFとし、等速かつrunning/pausedの間だけ有効にできる。10倍、100倍、最速では自動OFFとし、pause中は現在の仮想時刻の色で停止する。表示は校正済み物理光ではない。

`--headless-light-device-demo` は241 command/state、240 segment、20ms固定grid 12001 sampleと各digestをJSONで返す。CSVはcommand、stimulus state、segment、fixed-grid waveformの4種類であり、exportはsimulation stateやdigestを変えない。

標準fixtureでは180 active command、61 inactive command、180 active segment、60 inactive segmentとなる。最初のactive effective timeは `60,551,540 us`、最後は `239,589,850 us`、closing inactiveは `240,000,000 us` である。最初のholderは `life-green`、Hueは125.0 degree、BPMは87.5、phaseは0、Valueは0.425である。phase resetは1回、active continuationは179回、終了状態はinactive/Value 0、統合event数は3287である。

固定reference digestは次である。

- command: `306648650d4b286a48b3f9188f7fd640764b05fb135c581c4b9d00b487d06020`
- stimulus state: `1dbf214e1448802a665031f73fb798cdbf04471210aeddf438c68b72b616265e`
- segment: `9dabc1b018b52f9be603ba164655f3c5fa79ff4f6579ae8a6bfd48047d8fd763`
- fixed-grid waveform: `a075f488a588d7d2f78548e4ae339e7cac59c88f8e4508b2a89f0ca6e36cc0c0`
- full event: `f2ef166cd2bbea252d2c848b7f67d80cad1840534fe736d792087639b5b2a833`

これらは [Stage 6 reference vectors](conformance/stage-06-reference-vectors.json) とproduction-import非依存generatorで固定する。run-to-end、step、速度、reset、snapshot頻度、GUI有無、preview ON/OFF、CSV有無、config JSON round-tripで一致することをテストする。Stage 1〜5B.1の既存digestとCSVも回帰テストで維持する。

## Stage 7 interfaceと非実装範囲

Stage 7の唯一の正式光入力は `light_stimulus_state_event_v1` とする。Stage 6はこのeventを出力するだけで、VirtualUserのHeartbeat/RRI、生理、RMSSD、N/Nd/Wを変えない。Stage 5Cのcuriosity、trial、adoption、k探索も実装しない。
