# Participant adaptive effect classification v0.1

participant-levelの主結果はcontinuous paired effectである。最低限、autonomous−yoked/randomのlateΔRMSSD、late−early、session slope、selection enrichment、lagged couplingを個別に報告する。

`ParticipantClassificationPolicy`に保存する`participant_adaptive_effect_thresholds_v0_1`の分類はsimulation assumptionの補助診断で、binary primary outcomeではない。閾値はvalidation config/manifestに展開し、`formal_spec_adoption=false`をstrictに要求する。

- `clear_positive_adaptation`: late優位が0.5 msを超え、selection、slope、permutationを含む3条件以上がpositive。
- `partial_adaptation_signal`: positive条件が2つ以上。
- `no_clear_effect`: 上記を満たさず明確なnegativeでもない。正当な結果。
- `negative_or_unstable`: late優位が-0.5 ms未満でslopeもnegative。
- `insufficient_data`: valid sessionが4未満またはlate差がnull。

participant区間は同session indexのautonomous−yokedΔRMSSDを作り、late thirdに対しcontiguous block length 2の決定論的bootstrapを行う。user type・全体はparticipant-level effectをresamplingする。Bundle行を大量poolしない。閾値を全participantがpositiveになるよう調整しない。
