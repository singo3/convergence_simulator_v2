# 2×2 fatigue–sigma analysis v0.1

## 分析単位

すべてのpaired effectはparticipantを単位に計算する。1 participant内のBundle行やsession行を別participantとしてpoolしない。participantごとにA/B/C/Dと同一のshared-random comparatorを揃えてから、user typeと全体へ集約する。

## condition effect

条件ごとの主要指標は次のautonomous minus randomである。

- late-session mean ΔRMSSD
- late minus early ΔRMSSD
- session slope
- life selection enrichment
- BPM selection enrichment
- full-pattern selection enrichment
- lagged same-life coupling
- lagged pattern coupling

副次指標はcandidate/accepted/provisional count、W-ceiling blocked rate、holder switch rate、life share、final Hue/BPM、invalid rateである。

## factorial contrast

A=gradual×sigma1.0、B=gradual×sigma0.5、C=full×sigma1.0、D=full×sigma0.5とする。participantごとに次を保存する。

```text
sigma effect under gradual = B - A
sigma effect under full    = D - C
recovery effect at sigma1  = C - A
recovery effect at sigma.5 = D - B
interaction                = (D - C) - (B - A)
interaction alternate      = (D - B) - (C - A)
```

2つのinteractionが一致することを`interaction_identity_error`で監査する。少なくともlate ΔRMSSD advantage、late-minus-early、slope、full-pattern selection enrichment、lagged pattern coupling、autonomous holder-switch rate、accepted candidate countの7 outcomesに適用する。

## 不確実性

user type別と全体の平均に、決定論的participant bootstrapの95%区間を付ける。bootstrapの再標本化単位はparticipantであり、Bundle/sessionではない。欠損指標は代替値で埋めずnullとvalid participant countを保存する。

## 図の語彙

participant図は4 conditions×2 armsの8 panelを同一BPM scaleで示す。横軸はsession index、縦軸はblink BPM、塗り色はactual Hue、red/green/blue lifeの形は円/三角/四角である。Bundleはsession内offset、trialは半透明、代表値は大きい点で示す。加えて5指標のfactor plot、4指標のuser-type heatmap、A→B/C→D/A→C/B→Dのparticipant paired lineを保存する。

## 解釈境界

主効果とinteractionは観測専用で、Digital Life、Runtime、Garden、探索、session停止に介入しない。smokeは配線確認であり、条件判定の根拠にしない。
