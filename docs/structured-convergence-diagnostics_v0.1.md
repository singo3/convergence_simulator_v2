# Structured convergence diagnostics v0.1

`structured_convergence_diagnostics_v0_1`は正常完了したsession outcomeを1票とする読み取り専用の診断層である。holder ID、final committed BPM、表示用Hue、session validity/orderだけをprimary inputにし、Digital Life、Runtime、Garden、candidate、holder、k/q/E、探索係数、run停止条件を変更しない。

## Life dominance

直近8有効sessionを使う。同一Digital Lifeが6件以上、他生命が2件以下、かつ2件連続の非dominantがない場合にconfirmedとする。latestの単発outlierは許容する。dominant lifeの決定順は出現数、1-outlier tolerant最長区間、最新出現session、life ID lexicalである。HueとBPMはdominanceの条件に使わない。

出力はcount/share、strict run、1-outlier tolerant run、最長連続outlier、latest outlier、return-within-1/2、confirmed、first confirmed sessionである。

## Common BPM

直近8有効sessionから全subsetを決定論的に評価する。6件以上で`max BPM - min BPM <= 20`のsubsetが対象である。選択順はsupport大、range小、mean absolute deviation小、新しいsession多、session index tuple lexicalである。生命IDとHueを無視するため、赤・緑・青を横断した水平BPM帯もconfirmedにできる。

出力はsupport、member/outlier sessions、medoid/median BPM、range、mean absolute deviation、participating lives、cross-life、first confirmed sessionである。

## Life-specific multi-attractor

直近18有効sessionで生命ごとにBPM clusterを求める。各生命は出現数3以上、cluster support 3以上、support/occurrence 0.70以上、range 20 BPM以下を必要とする。有効attractorが2生命以上で、medoid BPMの最小間隔が20 BPM以上の場合にconfirmedとする。生命別のsupport、medoid、range、outlierと2/3-attractor flagを保存する。

## Summaryとearly signal

独立flagは`early_single_life_pattern_signal`、`life_dominant_converged`、`bpm_common_converged`、`multi_attractor_converged`、`three_attractor_converged`である。Stage 8Aの3-of-4 evaluatorは「早期の単一生命・近接パターン兆候」であり、新しい構造収束と同一視しない。

summaryは`insufficient_sessions`、`single_life_pattern_convergence`、`life_dominant_convergence`、`bpm_common_convergence`、`life_specific_multi_attractor_convergence`、`mixed_structured_convergence`、`diffuse_or_unresolved`のいずれかである。複数flagは消去せず保持し、summaryは単一最適スコアに使わない。

## Outlier、rotation、truth

単発outlier、return-within-1/2、収束後outlierを履歴として保持する。latest outlierだけで直ちにconvergence lostにしない。holder switch、3-distinct、A→B→A、A→B→C→A、dominant returnは疲労policyが作る機械的交代の診断であり、収束条件そのものではない。

hidden truth evaluatorはprimary evaluatorが確定した後にuser type v2のpeakを読み、structure mode、high-preference hit、dominant/common BPM/attractor alignment、flat-control spurious structureを診断する。hidden値をCoreへ返さない。
