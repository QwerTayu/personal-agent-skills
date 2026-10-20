"""集計するトークの設定（talks/<slug>/config.json）を読む。

recap を作るプロジェクトのディレクトリ（talks/ と data/ がある場所）で実行する。
スクリプトの最初の引数が slug。例: uv run <skill>/scripts/analyze.py alice-bob
プロジェクトの場所は環境変数 RECAP_ROOT でも指定できる。
"""
import os
import json
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ROOT = Path(os.environ.get("RECAP_ROOT", Path.cwd())).resolve()
TALKS = ROOT / "talks"


def _slug():
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        names = ", ".join(sorted(p.name for p in TALKS.iterdir() if p.is_dir())) if TALKS.exists() else "なし"
        sys.exit(f"集計するトークを指定してください（{ROOT}/talks にあるのは: {names}）")
    return args[0]


SLUG = _slug()
CONFIG = json.loads((TALKS / SLUG / "config.json").read_text())
STORY_PATH = TALKS / SLUG / "story.json"
DATA = ROOT / "data" / SLUG
RAW = DATA / "raw"
OUT = ROOT / "out" / SLUG
