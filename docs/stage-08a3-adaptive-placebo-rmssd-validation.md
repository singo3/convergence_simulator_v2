# Stage 8A.3 自律・プラセボRMSSD個人内適応検証

Stage 8A.3は、固定された光反応地形を持つ仮想参加者に対し、`autonomous_closed_loop`、`response_decoupled_yoked_replay`、`pure_random_open_loop`をpaired比較するpost-hoc simulation validation層である。`adaptive_placebo_rmssd_validation_v0_1`としてversion管理し、`formal_spec_adoption=false`を維持する。

## 位置づけ

`SimulationClock`、VirtualUser、H10、Garden入力、Digital Life、Garden出力、Light Mapper、Virtual Light Device、Stage 5C relation memoryは再実装しない。自律armはStage 8A.1 `FatigueSigmaSingleConditionRunner`を再利用する。open-loop armも既存のStage 3/4/6/7 componentを合成し、正式な`LightStimulusStateEvent`と`HeartbeatEvent`の境界を維持する。checkpoint、atomic write、fingerprint、lockはStage 8A.2の基盤を再利用する。

## 3 arm

- `autonomous_closed_loop`: target本人のHeartbeat→RRI→RMSSD→N→Nd/Wがq/k、holder競争、future B/Hue/BPMへ反映される唯一のarm。
- `response_decoupled_yoked_replay`: 同type・同conditionの別participantによるautonomous formal light state 241件/sessionを、local effective timeとpayloadを保って再生する。target RMSSD/N/W/q/k/Eは出力生成に接続しない。
- `pure_random_open_loop`: sessionごとにholderを1体選び3 Bundleで固定する。lifeの許容Hue帯と10〜165 BPMから決定論的randomに選び、RMSSD、condition、autonomous結果をkeyに入れない。

yoke mapは同type内でparticipant IDをsortしたcyclic mappingで、donorとtargetは必ず異なる。1人のtypeでは集計対象外のhidden donorを別seedで実行する。

## paired条件と主要尺度

同じparticipant・condition・sessionの3 armは、固定preference、response strength、physiology master/session seed、baseline/session/Bundle時間、artifact/RMSSD/N式、光物理写像を共有する。condition ID、arm ID、donor IDはphysiology seedに入れない。baseline中は光を出さず、3 arm一致を監査する。

セッションを跨ぐ主要生理値は `delta_rmssd_ms = bundle_rmssd_ms - baseline_rmssd_ms` である。Wはsession-local baselineに依存するalgorithm audit値として保存するが、異なるbaselineのWを長期尺度として直接比較しない。

## 時間方向を持つ分析

contemporaneous responseは同じBundleの光とΔRMSSDであり、yoked/randomでも生じ得る。BPMのPearson/Spearman、Hueの円環–線形相関、life別平均ΔRMSSDを`contemporaneous_response.csv`へ保存するが、本人のRMSSDが将来出力へ使われた証拠とは扱わない。主検証は過去sessionまでの反応が将来の選択を予測するlagged adaptive couplingと、過去履歴から高反応と予測された出力が後のΔRMSSDを改善するかというprospective benefitである。

history modelは必ずcurrent sessionより前のBundleだけを使う。life-only平均、BPM Gaussian kernel（bandwidth 15 BPM）、same-life + circular Hue Gaussian（5°）+ BPMのfull-pattern modelを保存する。minimum historyは3で、不足時は0ではなくnullとする。counterfactualは3 life × Hue 5位置 × BPM 11位置の165点である。hidden preference peakはobserved analysisに入れない。

## 統計と報告

participant内のsession label permutation null、one-step-ahead Pearson/Spearman/MAE/bias、early/middle/late、late−early、slope、paired arm differenceを出力する。participant別の95%区間はpaired late-sessionのcontiguous block bootstrap、user type/全体はparticipant bootstrapで計算する。分類は連続effectに従属する補助診断で、`no_clear_effect`を正当な結果とする。

reportは外部JavaScript、CDN、font、image URLのないinline CSS/SVG HTMLである。participant図は横軸session、縦軸BPM、actual HueをHSV色、life-red/green/blueを円/三角/四角で表す。user type平均はcircular Hue concentrationとlife share、全体図はparticipantを集計単位にする。

## 非目的

moving preference、context別anchor、人間実験の有効性、医療効果、臨床的有意差、Core係数の自動採用は対象外である。smokeは実装確認であり、有効性を主張しない。
