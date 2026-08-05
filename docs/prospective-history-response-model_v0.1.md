# Prospective history response model v0.1

`past_sessions_only_response_model_v0_1`は、session sの出力を予測する際、session 0〜s-1のvalid BundleOutcomeだけを学習に使う。session sのBundle 0/1/2、future session、hidden preference peakを使わない。各rowは`history_cutoff_session_index=s-1`を保存する。

## model

1. life-only: life IDが一致する過去ΔRMSSDの単純平均。
2. BPM-only: life/Hueを無視し、`exp(-0.5*(distance/15 BPM)^2)`のGaussian kernel regression。
3. full-pattern: same-lifeだけを対象に、circular Hue bandwidth 5°とBPM bandwidth 15の重みの積でregression。

各modelのminimum history countは3。不足ならnullとし、0で補完しない。bandwidthとcountはconfigとmanifestに保存する。

## counterfactualとone-step prediction

counterfactual setはred/green/blueの各lifeにつき、許容Hue帯の5等分位置と10〜165 BPMの11等分位置を組み合わせた165点。actual outputの予測値、counterfactual mean/median、percentile、actual minus meanをモデル別に保存する。

one-step-aheadは予測ΔRMSSDとsession sの実測平均ΔRMSSDのPearson、Spearman、MAE、signed bias、valid countを保存する。random armでも固定反応地形を学習できればprediction correlationは正になり得るため、相関単独を自律効果としない。
