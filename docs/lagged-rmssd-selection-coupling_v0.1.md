# Lagged RMSSD→selection coupling v0.1

`rmssd_to_future_output_coupling_v0_1`は、同時点反応と時間方向付き適応を分ける観測専用定義である。

contemporaneousはBundle sのactual life/Hue/BPMと同じBundleのΔRMSSDで、全armで生じ得る。laggedはsession sまでの応答とs+1以降のactual outputの関係である。主なparticipant・arm・condition別指標は次のとおり。

- session sの平均ΔRMSSDとs+1のsame-life indicatorのSpearman相関
- session sの平均ΔRMSSDとs+1のpattern closenessのSpearman相関
- 2 session以内のsame-life/near-pattern revisit
- selected life scoreから他2 life平均を引いたenrichment
- actual BPM/full pattern予測からcounterfactual平均を引いたenrichment
- 165点counterfactual分布内のselection percentile

pattern closenessはlife不一致を0とし、同一lifeではHue円環距離/5°とBPM距離/15を正規化した`1/(1+d)`である。participant内指標とparticipant-sessionを並べたscatterを混同しない。

permutation nullはparticipant内のsession-levelΔRMSSD labelだけをshuffleし、output sequence、session order、arm、valid/invalid patternを固定する。これはsimulation diagnosticであり、人間の臨床的有意差ではない。
