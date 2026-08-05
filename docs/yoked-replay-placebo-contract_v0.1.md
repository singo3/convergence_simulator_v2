# Yoked replay placebo contract v0.1

`response_decoupled_yoked_replay_v0_1`は、target本人の生理反応と将来出力の経路を切り離すsimulation placebo contractである。v2.0 Coreの規範ではなく、第30章の未確定事項を検証する実装仮定である。

1. 同じuser type・conditionの全target participantでautonomous armを先に完了する。
2. participant IDをsortし、次IDをdonorにするcyclic mapを作る。donorとtargetは必ず異なる。
3. 1 participantの場合は別physiology seedのhidden donorを実行し、target自身をdonorにしない。
4. donor autonomousの`LightStimulusStateEvent`由来recordをsession local effective time順に241件保存する。active/inactive、life ID、Hue、Saturation、Value parameter、BPM、waveform、source command/segment metadataをpayloadごと再生する。
5. targetでは既存のVirtualUser→Heartbeat→H10→RRI→Garden入力を実行しRMSSD/Nを観測するが、RMSSD、N、W、q、k、Eを光出力経路へ渡さない。

checksummed donor sequenceとmapにはtarget/donor participant、response strength、physiology master seed、condition、session/bundle、sequence digest、`cyclic_same_type_yoke_mapping_v0_1`を記録する。resumeは全donor checksumを先に検証し、不一致なら再生しない。

same-type yokeがautonomousと同程度なら、個人内適応の追加利益が小さい、type共通光系列で十分、session数不足、noiseが大きい等を候補理由とし、効果を作らない。
