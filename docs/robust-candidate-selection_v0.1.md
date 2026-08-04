# Robust candidate selection v0.1

## Balanced gate

`balanced_robust_candidate_gate_v0_1`の既定値は次である。これらはsimulation diagnosticの暫定gateであり、v2.0規範値ではない。

- failed replicate rate = 0
- valid session rate ≥ 0.95
- flat spurious structure rate ≤ 0.25
- flat mechanical rotation warning rate ≤ 0.25
- W ceiling blocked rate ≤ 0.50
- worst nonflat correct structure rate ≥ 0.30
- mean nonflat diffuse rate ≤ 0.50

Phase 1ではvalid ≥0.90、flat spurious ≤0.75、W ceiling ≤0.90、mean correct >0等の緩い`coarse_candidate_gate_v0_1`を使う。JSONでthresholdを変更できるが、結果に合わせて自動調整しない。

## Pareto

maximizeはworst/mean correct structureのlower95とreturn-within-2、minimizeはflat spurious/rotation/W ceilingのupper95、diffuse、初回構造session、post-convergence outlierである。missing値は有利に扱わず、binary64値をepsilonなしで比較する。各候補にrank、dominated by、dominates、objective vector、gate、blockerを保存する。

## Ranking

gate通過候補はworst lower95、mean lower95、flat safety、rotation、W ceiling、復帰、速度、outlier、低疲労、sigma=1への近さ、canonical axesの順にlexicographic比較する。opaque scoreは使わない。

specialistはlife dominance、BPM common、multi-attractor、low rotation、conservative compromiseを別々に示す。specialistにもflat safetyとW ceilingを必ず併記する。gate通過が0件なら`no_robust_candidate`を返し、Paretoとblockerは保持する。
