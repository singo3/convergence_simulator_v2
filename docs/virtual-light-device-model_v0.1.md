# Virtual PC Light Device model v0.1

## Contract

- model: `virtual_pc_light_device_v0_1`
- input: `light_command_event_v1`
- formal output: `light_stimulus_state_event_v1`
- audit segment: `light_stimulus_segment_v1`
- phase: `continuous_phase_integrator_v0_1`
- hold: `hold_until_next_command_v0_1`
- inactive: `light_off_black_v0_1`
- fixed sampling: `fixed_virtual_grid_20ms_v0_1`

DeviceはGarden/Digital Lifeを参照せず、Mapperが生成したLightCommandだけを適用する。各commandで前segmentを閉じ、新segmentを開始し、同時刻priority 67のformal stimulus stateを1件出力する。

Device coreはQt/PySide6/PyQtGraph/QColorに依存しない。GUIは正式な仮想時刻を引数に `state_at()` を呼び、返値を開発用previewに描画するだけである。

v2.0が規範として定めるのは、GardenがBから作ったIをfeedback deviceがユーザーへ提示する責務と、Relax with LightのHSV/sine parameterである。下記のanalytic phase、command hold、inactive black、state query、segment、priority、20ms gridは `virtual_pc_light_device_v0_1` が固定する **simulation implementation assumption** である。

## Analytic state

active commandの開始時刻`t0`、開始phase`p0`、BPM`b`に対して、`t>=t0`の位相は `(p0 + b(t-t0)/(60×10^6)) mod 1`、Valueは `center + amplitude sin(2πphase)` である。計算は絶対virtual microsecondsを用い、frame dtを累積しない。

`state_at(time_us)` はcommand/state履歴から現在・過去stateを再構成する。inactiveはphase null、Value 0である。queryは0〜simulation endを受理し、それ以降は拒否する。

同じphysical commandの再通知でもcommand record、state event、segment境界は追加するがphaseをresetしない。physical equivalenceへ含めるのはactive、formal Hue、Saturation、Value parameter、BPM、waveform、phase policyである。signal index、effective time、holder、event ID、source BのA/Dは含めない。Hue/BPMが変わるactive→activeも境界phaseを継承する。

## Segments and diagnostics

segmentは正時間の半開区間だけを保存する。隣接segmentのend/startを一致させ、gap/overlapを許さない。active同士の境界ではphase end/startを一致させる。simulation completeで最後の正時間segmentをendへclampする。

20ms waveform sampleはsimulation完了後に `state_at` から導出し、SimulationEngineへsample eventを登録しない。GUIの再描画頻度、preview ON/OFF、CSV exportはformal stateとdigestを変えない。

標準240秒scenarioでは241 command/state event、240 positive-duration segment、12001 fixed-grid sampleを生成する。closing inactive commandは240秒ちょうどに開始するためzero-duration segmentとして保存しない。

## Stage 7 boundary

`LightStimulusStateEvent` はsource B、HSV parameter、phase/value start、reset/equivalence/change flagとpolicy/schemaを含む。QColor/RGB pixel、RRI、N、Wは含まない。将来の光応答VirtualUserはGUIではなく、このeventだけを正式入力にできる。
