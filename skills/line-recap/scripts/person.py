"""集計するトークの設定（作業場所の config.json）を読む。

recap は 1 回ごとに作業場所（例: ~/Documents/line-recap/<slug>/）を 1 つ作り、そこにトークを 1 つだけ置く。
スクリプトは作業場所で引数なしで実行し、作業場所の中しか読まない。例: uv run <skill>/scripts/analyze.py
作業場所は環境変数 RECAP_ROOT でも指定できる。
"""
import os
import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("RECAP_ROOT", Path.cwd())).resolve()

if [a for a in sys.argv[1:] if not a.startswith("-")]:
    sys.exit("引数はいらない（作業場所で実行する。作業場所は 1 つのトーク専用）")
if not (ROOT / "config.json").exists():
    # ほかの作業場所があることも漏らさないよう、まわりのディレクトリは見ない
    sys.exit(f"{ROOT}/config.json がない（作業場所で実行する）")
CONFIG = json.loads((ROOT / "config.json").read_text())
STORY_PATH = ROOT / "story.json"
DATA = ROOT / "data"
RAW = DATA / "raw"
OUT = ROOT / "out"
