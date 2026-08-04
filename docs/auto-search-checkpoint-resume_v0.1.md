# Auto-search checkpoint / resume v0.1

run directoryは`search_manifest.json`、`search_plan.json`、`checkpoint.json`、`jobs.jsonl`、`completed_jobs/`、`failed_jobs/`、`reference_cache/`、`logs/`、`results/`、`report/`を持つ。

## Atomicity

JSON/JSONLは同じdirectoryの一時fileへwrite、flush、可能な範囲で`fsync`した後`os.replace`する。job開始前、各replicate/job完了後、conditionを含む各job境界、phase完了後、cancel request時にcheckpointを保存する。completed/failed resultはcanonical JSON SHA-256をwrapperとcheckpointへ保存する。

途中sessionは確定resultへ入れない。1回目のSIGINT/SIGTERMは現在session後の安全停止を要求し、running jobをpendingへ戻す。2回目はcheckpointをparse可能に保つ範囲で即時中断できる。resume時は残っていたrunning jobもpendingへ回復し、checksumが一致するcompleted jobだけをskipする。

## Strict resume

manifest、config、schema、code fingerprint、normative spec SHA、completed checksumを照合する。Git HEAD、clean flag、project/package version、Stage 8A.1/8A.2 version、spec SHA、Python、platformのfingerprintが異なる場合は`AUTO_SEARCH_CODE_CHANGED`で停止する。

run directoryの`.auto_search.lock`は`O_EXCL`で取得する。既存lockは古く見えても自動削除せず`AUTO_SEARCH_LOCKED`として内容を診断表示する。所有したlockだけを正常終了・例外時に削除する。
