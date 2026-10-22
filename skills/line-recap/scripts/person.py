"""集計するトークの設定（talks/<slug>/config.json）を読む。

recap を作るプロジェクトのディレクトリ（talks/ と data/ がある場所）で実行する。
スクリプトの最初の引数が slug。例: uv run <skill>/scripts/analyze.py alice-bob
プロジェクトの場所は環境変数 RECAP_ROOT でも指定できる。
"""
import os
import json
import re
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("RECAP_ROOT", Path.cwd())).resolve()
TALKS = ROOT / "talks"


def _slug():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        # ほかのトークがあることも漏らさないよう、talks/ の中身は一覧にしない
        sys.exit("集計するトークの slug を指定してください")
    # 「..」や絶対パスで、今回のトークの外（ほかのトークやプロジェクトの外）を読まないようにする
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args[0]):
        sys.exit("slug に使えるのは英数字と - _ だけです")
    return args[0]


SLUG = _slug()
CONFIG = json.loads((TALKS / SLUG / "config.json").read_text())
STORY_PATH = TALKS / SLUG / "story.json"
DATA = ROOT / "data" / SLUG
RAW = DATA / "raw"
OUT = ROOT / "out" / SLUG
