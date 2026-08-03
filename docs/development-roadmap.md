# Development roadmap

- 1. 時間シミュレーター: 完了
- 2. 外部刺激なし仮想ユーザー: 完了
- 3. 仮想Polar H10: 完了
- 4. Garden入力層とセッションシグナル: 完了
- 5A. 1体のデジタル生命・第1周: 完了
- 5B. 3生命・資格競争・第2周: 完了
- 5B.1. Garden出力境界・qualified B実効時刻補正: 完了
- 6. 光点滅シミュレーター: 完了
- 7. 固定反応特性の光応答仮想ユーザー: 完了
- 7.1. 物理光監査segment・response dynamics epoch分離: 完了
- 5C. 3Bundle関係記憶探索・確認型候補採否: 完了
- 8. 複数セッション状態引継ぎ・収束確認: 次工程
- 9. Webアプリ

Stage 7はStage 6の `LightStimulusStateEvent` だけをformal inputとし、固定Hue/BPM嗜好、一次遅れresponse、平均RRI・呼吸性RRI変動幅を介して既存 `HeartbeatEvent` へ閉ループ接続した。Stage 7.1は物理parameterの監査segmentとtarget変更のresponse dynamics epochを分離したが、生理式とformal event streamは変更しない。GUI preview、segment、20ms waveform sample、holder/source Bを生理入力にしない。

Stage 5Cはこの閉ループに、各Digital Life内部の `adaptive_random_search_confirmed_v1` を追加した。Bundle 0でanchorを評価し、決定論的にhold/exploreを選び、最大1つのF/T candidateをBundle 1/2で仮評価・確認する。persistent state入出力は次工程のinterfaceとして用意するが、Stage 5Cはsingle-sessionだけを実行し、複数sessionの自動引継ぎやconvergenceを評価しない。Stage 8はこのstrict state seamの上にbaseline lifecycle、multi-session runner、収束確認を追加する次工程である。
