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
- 8A. 固定好み・複数セッション収束ラボ: 完了
- 8B. 変化する好み・追従性: 次工程
- 8C. 探索係数比較: 後続
- 9. Webアプリ

Stage 7はStage 6の `LightStimulusStateEvent` だけをformal inputとし、固定Hue/BPM嗜好、一次遅れresponse、平均RRI・呼吸性RRI変動幅を介して既存 `HeartbeatEvent` へ閉ループ接続した。Stage 7.1は物理parameterの監査segmentとtarget変更のresponse dynamics epochを分離したが、生理式とformal event streamは変更しない。GUI preview、segment、20ms waveform sample、holder/source Bを生理入力にしない。

Stage 5Cはこの閉ループに、各Digital Life内部の `adaptive_random_search_confirmed_v1` を追加した。Bundle 0でanchorを評価し、決定論的にhold/exploreを選び、最大1つのF/T candidateをBundle 1/2で仮評価・確認する。Stage 8Aはこのstrict state seamを使い、固定user landscapeの下で正常終了stateを次sessionへ渡し、毎session baselineと`W_anchor_session`を取り直す。一次収束は完了sessionを独立票とする観測専用の3-of-4 rolling診断であり、探索を停止しない。moving preferenceはStage 8B、係数比較はStage 8Cへ残す。
