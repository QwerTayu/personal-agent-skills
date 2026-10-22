"""data/raw/ の txt を読み、メッセージ・通話・システムメッセージの表にする。

送り手は config.json の members で呼び名に置き換え、以降は txt の表示名を使わない。
人は key（本人が p0、ほかは件数の多い順に p1, p2, …）で表す。
"""
import collections
import re
import sys
import unicodedata
from datetime import date

import pandas as pd

from parse_line import YOU, parse
from person import CONFIG, RAW

# 集計する範囲（config.json の since / until。"2026-04-01" の形。どちらも含む）
SINCE = date.fromisoformat(CONFIG["since"]) if CONFIG.get("since") else None
UNTIL = date.fromisoformat(CONFIG["until"]) if CONFIG.get("until") else None
MODE = CONFIG.get("mode", "pair")

# 口座・連絡先・住所などを含むメッセージは、だれのものでも使わない。
# 全角の数字やハイフンもあるので、sensitive() で正規化してから探す
SENSITIVE_RE = re.compile(
    r"口座|銀行|支店|名義|暗証|パスワード|住所|〒|振込|振り込み先|ゆうちょ|カード番号|マイナンバー|生年月日"
    r"|(?<![\d+])0\d{9,10}(?!\d)|(?<![\d+])0\d{1,4}[- ]\d{1,4}[- ]\d{4}(?!\d)"  # 電話番号
    r"|\+81[- ]?\d{1,4}[- ]?\d{1,4}[- ]?\d{4}(?!\d)"  # 電話番号（国番号から）
    r"|(?<![\d-])\d{3}-\d{4}(?![\d-])"  # 郵便番号
    r"|(?<!\d)\d{4}(?:[- ]?\d{4}){3}(?!\d)"  # カード番号
    r"|[\w.+-]+@[\w-]+\.[\w.-]+"  # メールアドレス
    r"|[都道府県]\S{1,8}[市区町村]\S{0,12}\d+[-丁]\d+"  # 番地まである住所
    r"|[市区町村]\S{0,12}?\d+-\d+-\d+"  # 都道府県のない住所（渋谷区神南1-2-3）
    r"|(?:\d+|[一二三四五六七八九十]+)丁目\s*\d+|\d+番地|\d+番\d+号"  # 丁目・番地
)
# 数字のあいだの長音やダッシュ（090ー1234ー5678 など）
_DASH_RE = re.compile(r"(?<=\d)[ー‐‑‒–—―−](?=\d)")


def sensitive(text):
    return bool(SENSITIVE_RE.search(_DASH_RE.sub("-", unicodedata.normalize("NFKC", text))))

URL_RE = re.compile(r"https?://\S+")
# LINE の絵文字は本文の中で (emoji) (good) のような括弧の英単語になる
LINE_EMOJI_RE = re.compile(r"\(([a-z][a-z ]{0,20})\)")
EMOJI_RE = re.compile("[\U0001F000-\U0001FAFF☀-➿⬀-⯿]")


def _txt():
    files = sorted(RAW.glob("*.txt"))
    if len(files) != 1:
        sys.exit(f"{RAW} に txt を 1 つだけ置いてください（今は {len(files)} 個）")
    return files[0]


def _in_range(dt):
    d = dt.date()
    return (SINCE is None or d >= SINCE) and (UNTIL is None or d <= UNTIL)


TALK = parse(_txt())
for _w in TALK["warnings"]:
    print(f"注意: {_w}", file=sys.stderr)

_alias = CONFIG.get("sender_aliases", {})
_members = CONFIG.get("members", {})
ME_NAME = CONFIG["me"]


def _sender(name):
    return _alias.get(name, name)


def _people():
    """送り手の表示名 → key と、key → 呼び名。"""
    counts = collections.Counter(_sender(it["sender"]) for it in TALK["items"]
                                 if it.get("sender") and _in_range(it["dt"]))
    if ME_NAME not in counts:
        sys.exit(f"config.json の me（{ME_NAME}）が送り手にいません。parse_line.py で送り手の一覧を確かめてください")
    order = [ME_NAME] + [n for n, _ in counts.most_common() if n != ME_NAME]
    if MODE == "pair" and len(order) != 2:
        sys.exit(f"1 対 1 モードなのに送り手が {len(order)} 人います。sender_aliases でまとめるか、mode を group にしてください")
    # 呼び名は全員分をユーザーに聞いて書く（「メンバーA」のような仮の名前は出さない）
    missing = [n for n in order if not _members.get(n)]
    if missing:
        sys.exit("config.json の members に呼び名がない送り手がいます。全員の呼び名をユーザーに聞いて書いてください:\n"
                 + "\n".join(f"  {n}（{counts[n]} 件）" for n in missing))
    key_of = {n: f"p{i}" for i, n in enumerate(order)}
    people = [dict(key=f"p{i}", name=_members[n], is_me=i == 0, n=counts[n]) for i, n in enumerate(order)]
    return key_of, people


KEY_OF, PEOPLE = _people()
NAME_OF = {p["key"]: p["name"] for p in PEOPLE}
ME = "p0"


def load():
    """メッセージ（本文とメディア）・通話・システムメッセージの表を返す。"""
    msgs, calls, system = [], [], []
    dropped = 0
    for it in TALK["items"]:
        if not _in_range(it["dt"]):
            continue
        if it["kind"] == "system":
            who = it.get("who")
            key = ME if who == YOU else KEY_OF.get(_sender(who)) if who else None
            system.append(dict(dt=it["dt"], event=it["event"], who=key))
            continue
        who = KEY_OF[_sender(it["sender"])]
        if it["kind"] == "call":
            calls.append(dict(dt=it["dt"], who=who, status=it["status"], sec=it.get("sec")))
            continue
        text = it.get("text", "")
        if it["kind"] == "text" and sensitive(text):
            dropped += 1
            continue
        msgs.append(dict(dt=it["dt"], seq=it["seq"], who=who, kind=it["kind"], text=text))
    if dropped:
        print(f"個人情報らしい語（口座・電話番号・住所・メールアドレスなど）を含むメッセージを {dropped} 件外した", file=sys.stderr)
    df = pd.DataFrame(msgs, columns=["dt", "seq", "who", "kind", "text"])
    if df.empty:
        sys.exit("範囲の中にメッセージがありません。config.json の since / until を確かめてください")
    df = df.sort_values(["dt", "seq"]).reset_index(drop=True)
    df["is_text"] = df.kind == "text"
    df["link_only"] = df.is_text & df.text.str.fullmatch(r"\s*https?://\S+\s*")
    df["plain"] = df.text.map(clean)
    return df, calls, system, dropped


def _mention_names():
    names = set(KEY_OF) | set(_alias)
    return sorted(names, key=len, reverse=True)


MENTION_NAMES = _mention_names()


def clean(text):
    """URL・LINE の絵文字・メンションを除く。"""
    t = URL_RE.sub(" ", text)
    t = LINE_EMOJI_RE.sub(" ", t)
    for n in MENTION_NAMES:
        t = t.replace("@" + n, " ")
    return t
