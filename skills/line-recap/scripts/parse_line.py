"""LINE のトークを書き出した txt（iOS・英語表示）を読む。標準ライブラリだけで動く。

Usage: python3 <skill>/scripts/parse_line.py <txt>
txt の見出し・期間・送り手の一覧・メディアやシステムメッセージの件数を表示する。
config.json を書く前に、モード・範囲・本人がだれかを決めるのに使う。

ほかのスクリプトからは parse(path) を呼ぶ。
"""
import collections
import re
import sys
from datetime import date, datetime, timedelta

# 文言の表。ほかの表示言語に対応するときは、ここに足す
HEADER_RE = re.compile(r"^﻿?\[LINE\] Chat history (with|in) (.*)$")
SAVED_RE = re.compile(r"^Saved on: (\d{4})/(\d{2})/(\d{2}),? (\d{1,2}):(\d{2})")
DATE_RE = re.compile(r"^(\d{4})/(\d{2})/(\d{2}) (?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)$")
MSG_RE = re.compile(r"^(\d{1,2}):(\d{2})\t([^\t]*)\t(.*)$")
MEDIA = {
    "Sticker": "sticker", "Photo": "photo", "Video": "video", "Voice message": "voice",
    "File": "file", "Location": "location", "Contact": "contact", "Album": "album",
}
MEDIA_RE = re.compile(r"^\[([^\]\n]+)\]$")
CALL_TIME_RE = re.compile(r"^☎ Call time (\d+(?::\d{2}){1,2})$")
CALLS = {"☎ Missed call": "missed", "☎ No answer": "no_answer", "☎ Canceled call": "canceled",
         "☎ Group call started.": "group_start"}
UNSENT_RE = re.compile(r"^(.+) unsent a message\.$")
SYSTEM_KINDS = [
    ("group_call_end", re.compile(r"^Group call ended\.$")),
    ("member", re.compile(r" (added .+ to the group|removed .+ from the group|joined the group|left the group)\.$")),
    ("announce", re.compile(r" made an announcement\.$")),
    ("group_change", re.compile(r" changed the group's (name|profile picture)")),
]
# 名前を囲む方向の分離の記号（U+2068, U+2069）
ISOLATES = str.maketrans("", "", "⁨⁩")
YOU = "You"


def _seconds(s):
    sec = 0
    for p in s.split(":"):
        sec = sec * 60 + int(p)
    return sec


def _item(d, hh, mm, sender, body):
    """メッセージの行を 1 件の dict にする。"""
    dt = datetime(d.year, d.month, d.day, int(hh), int(mm))
    sender = sender.translate(ISOLATES)
    if not sender:
        body = body.translate(ISOLATES)
        m = UNSENT_RE.match(body)
        if m:
            return dict(dt=dt, kind="system", event="unsent", who=m.group(1))
        event = next((k for k, r in SYSTEM_KINDS if r.search(body)), "other")
        return dict(dt=dt, kind="system", event=event, text=body)
    m = CALL_TIME_RE.match(body)
    if m:
        return dict(dt=dt, kind="call", sender=sender, status="answered", sec=_seconds(m.group(1)))
    if body in CALLS:
        return dict(dt=dt, kind="call", sender=sender, status=CALLS[body])
    if body.startswith("☎"):
        return dict(dt=dt, kind="call", sender=sender, status="other", text=body)
    m = MEDIA_RE.match(body)
    if m and m.group(1) in MEDIA:
        return dict(dt=dt, kind=MEDIA[m.group(1)], sender=sender)
    if m and "\n" not in body and re.fullmatch(r"[A-Z][A-Za-z ]{1,30}", m.group(1)):
        # 知らない種類のメディア。読み込んだときに一覧を出す
        return dict(dt=dt, kind="other_media", sender=sender, label=m.group(1))
    return dict(dt=dt, kind="text", sender=sender, text=body)


def parse(path):
    lines = open(path, encoding="utf-8").read().replace("\r\n", "\n").split("\n")
    m = HEADER_RE.match(lines[0]) if lines else None
    if not m:
        sys.exit(f"{path} の 1 行目が LINE の書き出しの見出し（[LINE] Chat history with/in …）ではありません。"
                 "iOS・英語表示の書き出しだけに対応しています")
    mode = "pair" if m.group(1) == "with" else "group"
    title = m.group(2).translate(ISOLATES)
    s = SAVED_RE.match(lines[1]) if len(lines) > 1 else None
    saved_on = datetime(*map(int, s.groups())) if s else None

    rows, warnings = [], []
    day, quoted = None, False  # quoted: " で始まった複数行の本文の途中
    for no, line in enumerate(lines[2:], start=3):
        mm = MSG_RE.match(line)
        if quoted:
            if mm:
                # 閉じの " がないまま次のメッセージが来た。ここで閉じる
                warnings.append(f"{no} 行目: 前の本文の閉じの \" がない")
                quoted = False
            else:
                rows[-1][4] += "\n" + line
                if line.endswith('"'):
                    quoted = False
                continue
        d = DATE_RE.match(line)
        if d:
            day = date(*map(int, d.groups()))
            continue
        if mm:
            if day is None:
                warnings.append(f"{no} 行目: 日付の行より前にメッセージがある")
                continue
            hh, mi, sender, body = mm.groups()
            rows.append([day, hh, mi, sender, body])
            if body.startswith('"') and not (len(body) > 1 and body.endswith('"')):
                quoted = True
            continue
        if line == "":
            continue
        if rows:
            # どの形にも当てはまらない行は、前の本文の続きとみなす
            warnings.append(f"{no} 行目: どの形にも当てはまらないので、前の本文につなげた")
            rows[-1][4] += "\n" + line
        else:
            warnings.append(f"{no} 行目: どの形にも当てはまらないので、読み飛ばした")
    if quoted:
        warnings.append("最後の本文の閉じの \" がない")

    items = []
    for day, hh, mi, sender, body in rows:
        if "\n" in body and body.startswith('"'):
            # 閉じの " がないまま終わった本文は、始めの " だけを外す
            body = body[1:-1] if body.endswith('"') else body[1:]
        it = _item(day, hh, mi, sender, body)
        it["seq"] = len(items)
        items.append(it)
    return dict(title=title, mode=mode, saved_on=saved_on, items=items, warnings=warnings)


def senders(items):
    return collections.Counter(it["sender"] for it in items if it.get("sender"))


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    t = parse(sys.argv[1])
    items = t["items"]
    if not items:
        sys.exit("メッセージがありません")
    first, last = items[0]["dt"].date(), items[-1]["dt"].date()
    snd = senders(items)
    kinds = collections.Counter(it["kind"] for it in items)
    print(f"トーク名: {t['title']}")
    print(f"モードの見当: {'1 対 1（pair）' if t['mode'] == 'pair' else 'グループ（group）'}（見出しが Chat history {'with' if t['mode'] == 'pair' else 'in'}）")
    print(f"保存日時: {t['saved_on']:%Y-%m-%d %H:%M}" if t["saved_on"] else "保存日時: なし")
    print(f"期間: {first} 〜 {last}（{(last - first).days + 1} 日）")
    print(f"直近 1 年なら since: {max(first, last - timedelta(days=364))}")
    print(f"件数: {len(items)}（{', '.join(f'{k} {n}' for k, n in kinds.most_common())}）")
    print(f"送り手（{len(snd)} 人）:")
    for name, n in snd.most_common():
        print(f"  {n:6d}  {name}")
    if t["mode"] == "pair":
        me = [s for s in snd if s != t["title"]]
        print(f"本人の見当: {me[0] if len(me) == 1 else '（決められない。送り手の一覧から選ぶ）'}")
    unsent = collections.Counter(it["who"] for it in items if it.get("event") == "unsent")
    if unsent:
        print(f"送信取り消し: {dict(unsent)}（{YOU} は本人）")
    sysev = collections.Counter(it["event"] for it in items if it["kind"] == "system")
    if sysev:
        print(f"システムメッセージ: {dict(sysev)}")
    calls = collections.Counter(it["status"] for it in items if it["kind"] == "call")
    if calls:
        print(f"通話: {dict(calls)}")
    other = collections.Counter(it["label"] for it in items if it["kind"] == "other_media")
    if other:
        print(f"知らない種類のメディア（parse_line.py の MEDIA に足すとよい）: {dict(other)}")
    other_calls = collections.Counter(it["text"] for it in items if it["kind"] == "call" and it["status"] == "other")
    if other_calls:
        print(f"知らない通話の文言（parse_line.py の CALLS に足すとよい）: {dict(other_calls)}")
    for w in t["warnings"][:20]:
        print(f"注意: {w}")
    if len(t["warnings"]) > 20:
        print(f"注意: ほかに {len(t['warnings']) - 20} 件")


if __name__ == "__main__":
    main()
