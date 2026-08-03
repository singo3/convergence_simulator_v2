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
- 5C. 3 bundle関係記憶探索: 次工程
- 8. 全閉ループ適応・複数セッション
- 9. Webアプリ

Stage 7はStage 6の `LightStimulusStateEvent` だけをformal inputとし、固定Hue/BPM嗜好、一次遅れresponse、平均RRI・呼吸性RRI変動幅を介して既存 `HeartbeatEvent` へ閉ループ接続した。Stage 7.1は物理parameterの監査segmentとtarget変更のresponse dynamics epochを分離したが、生理式とformal event streamは変更しない。GUI preview、segment、20ms waveform sample、holder/source Bを生理入力にしない。次工程のStage 5Cでは3 bundle関係記憶探索を実装するが、Stage 7のformal user boundaryと固定preference modelを変更しない。
