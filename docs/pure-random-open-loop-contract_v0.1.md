# Pure random open-loop contract v0.1

`pure_random_open_loop_v0_1`は、targetの生理結果から完全に独立した光出力対照である。

- keyはvalidation master seed、participant ID、session index、bundle index、random-output roleだけを含む。
- RMSSD、N、W、condition fatigue/sigma、autonomous結果、convergenceをkeyまたは後続選択に使わない。
- holderはred/green/blueからsessionごとに決定論的uniformに1体選び、3 Bundleで固定する。
- BundleごのFはholderの許容帯内、Tはunit intervalから選び、既存Mapperにより`Hue=360F`、`BPM=10+155T`とする。A/D、Saturation、Value、sine waveformは既存Garden設定を維持する。
- 同じparticipant/sessionのsequenceはcondition間で再利用可能である。

targetのVirtualUser/H10/Garden入力は光へのRMSSDを測定するが、open-loopにq/k適応、candidate、committed anchorは存在しない。
