#!/bin/bash

set -u

SCRIPT_DIR="$(cd -- "$(dirname -- "$0")" && pwd)"
cd "$SCRIPT_DIR" || {
  echo "プロジェクトの場所へ移動できませんでした。"
  read -r -p "Returnキーで終了します。"
  exit 1
}

if [ ! -x ".venv/bin/python" ]; then
  echo "仮想環境 .venv が見つかりません。"
  echo "Terminalでこのフォルダを開き、README.mdのSetup手順を実行してください。"
  echo "例: python3.13 -m venv .venv"
  echo "続けて: .venv/bin/python -m pip install -e '.[dev]'"
  read -r -p "Returnキーで終了します。"
  exit 1
fi

source ".venv/bin/activate"
python -m symbiotic_sim_v2
APP_STATUS=$?
deactivate

if [ "$APP_STATUS" -eq 0 ]; then
  echo "時間シミュレーターを終了しました。"
else
  echo "時間シミュレーターはエラー（終了コード: $APP_STATUS）で終了しました。"
fi
read -r -p "Returnキーでこのウインドウを閉じます。"
exit "$APP_STATUS"
