# 環境共生型デジタル生命シミュレーター v2

環境共生型デジタル生命システムの各構成要素を、将来同じ決定論的な仮想時間上で動かすためのPythonプロジェクトです。現在実装済みなのは **Stage 1「時間シミュレーター」だけ**です。20秒の診断用Demoを使い、整数microsecondsの仮想時計、イベント予約・配送、停止・再開・step・reset、速度非依存の実行結果をGUIまたはheadlessで確認できます。

このDemoは時間基盤の診断専用で、将来の実システムモデルではありません。仮想ユーザー、Polar H10、セッションシグナルS、Garden、デジタル生命、光刺激はまだ実装していません。

## 採用ライブラリ

- Python 3.12以上（開発環境は3.13）
- PySide6 / Qt Widgets
- PyQtGraph / NumPy
- pytest / pytest-qt
- Ruff
- `pyproject.toml` と `src` layout

## Setup

プロジェクト直下に仮想環境 `.venv` を1つだけ作り、editable installします。

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e '.[dev]'
```

Python 3.13がない環境では、Python 3.12以上の実行ファイルへ読み替えてください。以後の更新でも同じ `.venv` を再利用します。

## 起動

GUI:

```bash
.venv/bin/python -m symbiotic_sim_v2
```

macOSでは、実行権限付きの `時間シミュレーターを起動.command` をダブルクリックしても起動できます。launcherは自身の場所をproject rootとして扱い、`.venv` がなければ日本語のsetup案内を表示して停止します。

Headless診断:

```bash
.venv/bin/python -m symbiotic_sim_v2 --headless-demo
```

GUI smoke（1.5秒以内に操作列を実行して自動終了）:

```bash
QT_QPA_PLATFORM=offscreen .venv/bin/python -m symbiotic_sim_v2 \
  --smoke-test --auto-close-ms 1500
```

## GUIの操作

- `開始`：選択した速度で自動進行を開始します。
- `一時停止` / `再開`：自動進行だけを止め、同じ仮想時刻から再開します。
- `リセット`：時計、queue、実行履歴、event ID、sequence、診断値を初期状態へ戻します。
- `1秒進む`：正確に1,000,000 microseconds進み、その区間で到達した全イベントを実行します。
- `次イベント`：次のイベントを正確に1件だけ実行します。同時刻の次イベントは次回まで残ります。
- `最後まで実行`：wall-time待機なしのbounded batchへ切り替え、完了まで実行します。
- `等速 / 10倍 / 100倍 / 最速`：実時間上の進行方法だけを変更します。最終event列とdigestは変わりません。

画面には上部ステータス、PyQtGraphタイムライン、実行済みイベントだけのログ、wall timeとvirtual timeの診断値を表示します。

## 仮想時計とQTimer

正式な時刻はcoreの `SimulationClock.current_time_us` であり、整数microsecondsです。QTimerはGUI controllerを定期的に起こすだけで、正式な時計でもevent発火源でもありません。等速・10倍・100倍では `time.perf_counter_ns()` の差分を整数演算でvirtual microsecondsへ変換します。最速では実時間差を使わず、1 callbackあたりの最大件数とwall-time budgetを持つbatchを実行してGUIへ制御を返します。

描画頻度やcallbackの分割が変わっても、coreは到達targetまでのeventをqueue順に処理するため、実行結果は同じです。

## Event ordering

queueの比較キーは次の昇順で固定しています。

1. `scheduled_time_us`
2. `priority`（小さい値が先）
3. `sequence`（登録順の単調増加整数）

Demoでは7.3秒のBを先に登録し、Aへ小さいpriorityを与えています。そのためA、Bの順になり、20秒では `clock_tick`、`simulation_complete` の順になります。reset後は同じevent ID、sequence、実行順、SHA-256 digestを再現します。

## Test / lint

```bash
.venv/bin/python -m compileall -q src tests
QT_QPA_PLATFORM=offscreen .venv/bin/pytest -q
.venv/bin/ruff check .
```

テストはclock lifecycle、scheduler、cancel、handlerによる未来event追加、step semantics、reset決定性、4速度相当のchunking、headless、offscreen GUI操作、timeline/log更新、window close時のQTimer停止を対象にします。core packageはPySide6/PyQtGraphをimportしません。

## 今回未実装のもの

仮想ユーザー、心拍/RRI/HRV、Polar H10、セッションシグナルS、baseline、bundle、Garden入力・出力、デジタル生命、P/Nd/W/E/q/V/B/G/τ、ハンドル競争、光出力、Web、DB、network、Monte Carlo、収束判定はStage 1の対象外です。RuntimeによるP/V比較や勝者選択も実装していません。

次工程は **外部刺激を受けない仮想ユーザー** ですが、本Stageには先回りして含めていません。設計の詳細は [Stage 1設計](docs/stage-01-time-simulator.md)、規範との境界は [規範スコープ](docs/normative-scope.md)、順序は [roadmap](docs/development-roadmap.md) を参照してください。
