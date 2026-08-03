# Stage 8A 固定好み・複数セッション収束ラボ

Stage 8Aは、Stage 5Cの240秒single-session factoryを実行単位として複数回連結する、GUI非依存の診断orchestration層である。Digital Life、Runtime、Gardenのcandidate生成・採否・holder規則は変更しない。

## 1セッションの境界

各sessionは独立した`SimulationEngine`を持ち、local virtual timeは`0..240,000,000 µs`である。集計上の時刻だけを次で表す。

```text
global_time_offset_us = session_index * 240,000,000
global_time_us = global_time_offset_us + local_time_us
```

正常なclosing後だけ`k_anchor`、`q`、`E`、`trial_count`、`session_count`とversion metadataを次sessionへcommitする。各sessionではbaselineを再取得し、N/Nd/W、`W_anchor_session`、trial、資格holder、light command、response dynamicsなどのsession-local stateを新規生成する。errorまたは未完了sessionではstateをcommitせず、その時点でrunを停止する。

## 固定ユーザーと生理揺らぎ

user typeと全preference peakはrun中に固定する。sessionごとに変えてよいのは、version管理されたseed policyによるStage 2生理noiseだけである。moving preference、時間帯・気温・疲労依存はStage 8Bへ残す。

Stage 8AはStage 5Cの正式red/green/blue rosterと係数、Stage 2の既定physiology templateを固定する。任意ID・role係数・平均心拍やRSA設定の差し替えは許可せず、sessionごとに変化させるのは`VirtualUserConfig.root_seed`だけとする。これによりstrict JSON resumeで保存対象外のtemplateが差し替われる余地をなくす。

## 収束の意味

収束とは探索停止ではなく、同じDigital Lifeと近しい正式Hue/BPM patternがrolling履歴の多数を占める観測状態である。1sessionの3Bundleは同じ資格holderを共有するため独立票にせず、正常完了した1sessionを1票とする。代表patternはsession終了後にcommitされたholderの`k_anchor`から算出する。

既定条件は直近4有効session中3sessionである。最新sessionがoutlierでも残り3件がpairwise近傍clusterなら収束を維持する。収束後も`p_explore_min`と`sigma_min`によるStage 5C探索は`maximum_sessions`まで続く。

primary convergence evaluatorが見るのはholder ID、final committed Hue/BPM、session validityだけである。hidden preference peakやresponse gapは別のsimulation-only truth diagnosticだけが使用し、Digital Life、Runtime、Gardenへ返さない。

各Bundleで物理的に提示されたpatternは収束票に使わない一方、`BundleLightPresentation`へ連続segmentとして保存する。segmentはBundle index、signal範囲、effective time範囲、holder、提示k/B、formal Hue/BPM、mapping versionを持つ。これにより120秒・180秒のnext-signal境界で旧patternが1signalだけ残る場合も失わず、GUI timeline、rejected-trial marker、pattern trajectory CSV、strict state JSONが同じ監査値を使う。

## Hidden truth alignment

truth alignment versionは`stationary_landscape_truth_alignment_v0_1`であり、一次収束判定の後にだけ計算する。medoidのpreference matchを`m_medoid`、profile内peak weightの最大を`m_global`とし、response gapは次である。

```text
response_gap = max(0, m_global - m_medoid)
```

- `not_converged`: primary clusterが未成立
- `correct_convergence`: primary cluster成立かつ`response_gap <= truth_response_gap_threshold`
- `stable_suboptimal`: primary cluster成立かつ上記thresholdを超える
- `no_preference_control`: peakを持たない`flat_control`。正解収束を主張せず、match/gap/nearest peakをnullとする

nearest peakは表示・監査専用のsimulation assumptionである。各peakについてHue円環距離とBPM差をそのpeak自身のsigmaで正規化し、次の距離が最小のpeakを選ぶ。同距離ならpeak ID lexical順とする。

```text
d_peak = sqrt(
  (circular_hue_distance / peak.hue_sigma_degree)^2
  + (bpm_difference / peak.blink_sigma_bpm)^2
)
```

このID・距離、preference match、global maximum、response gap、classificationはGUIとimmutableなtruth監査recordに表示・保存する。headless summaryはnearest peak ID、CSVはresponse gapとclassificationを含む。いずれもDigital Life、Runtime、Garden、candidate選択、session停止へ入力しない。

## Resume authority

`--initial-multi-session-state-json`を指定した場合、JSON内のuser type、master seed、seed policy、rolling config、version tupleをauthoritativeとする。CLIの既定option値で上書きまたは不一致扱いにしない。各outcomeのfull initial persistent stateと直前outcomeのfinal stateをexact比較し、`k_anchor/q/E/trial_count/session_count`およびversion metadataのchainが切れたstateは拒否する。

## 実装しないもの

- moving/context-dependent preference
- convergenceによる探索停止や係数上書き
- v2.0探索係数のtuning
- Monte Carlo
- Web/DB/network/ML

詳細は[rolling majority定義](rolling-majority-convergence-definition_v0.1.md)、[固定user landscape](stationary-user-type-landscapes_v0.1.md)、[state handoff](multi-session-state-handoff_v0.1.md)、[session seed policy](session-physiology-seed-policy_v0.1.md)を参照する。
