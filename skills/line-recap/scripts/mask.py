"""引用する本文の名前を伏せる。recap.json に書く前に使う。

- txt の表示名（config.json の members と sender_aliases のキー）とその一部は、members の呼び名に置き換える
- そのほかの名前（config.json の nicknames）は、ユーザーに聞いた表示に置き換える（{名前: 表示する文字列}。
  リストで書いたものは「〇〇」）。2 文字以下の名前は、敬称が続くときと Sudachi で 1 語に切れたときだけ置き換える
- URL はドメインだけにし、LINE の絵文字の (emoji) (null) は消す
"""
import re

from person import CONFIG

_members = CONFIG.get("members", {})
_alias = CONFIG.get("sender_aliases", {})
# 表示名 → 呼び名。長い名前から置き換える（短い名前が長い名前の一部のことがある）
_RENAME = {n: _members[_alias.get(n, n)] for n in set(_members) | set(_alias) if _alias.get(n, n) in _members}

# 表示名の一部（「山田 花子（はな）」の「花子」「はな」など）で呼ばれることもあるので、それも置き換える。
# 数字だけの部分（学籍番号など）と、1 文字の部分は使わない
def name_parts(name):
    parts = {p for p in re.split(r"[\s()（）・_/@]+", name) if len(p) >= 2 and not p.isdigit()}
    return {p for p in parts if not p.isascii() or len(p) >= 3} - {name}


for _n, _nick in list(_RENAME.items()):
    for _p in name_parts(_n):
        _RENAME.setdefault(_p, _nick)
_RENAME = sorted(_RENAME.items(), key=lambda x: -len(x[0]))
# nicknames は、ページに出すときの名前をユーザーに聞いて {名前: 表示する文字列} で書く
_nick = CONFIG.get("nicknames", [])
NICKNAMES = sorted((_nick.items() if isinstance(_nick, dict) else ((n, "〇〇") for n in _nick)),
                   key=lambda x: -len(x[0]))
# 2 文字以下の名前（「太郎」など）は、文字列の一部として置き換えると普通の語や別の名前を壊す（「太郎丸」、「ゆう」なら「ゆうがた」）。
# 敬称が続くときと、Sudachi で 1 語に切れたときだけ置き換える
SHORT = {n: to for n, to in NICKNAMES if len(n) < 3}
NICKNAMES = [(n, to) for n, to in NICKNAMES if len(n) >= 3]
HONORIFIC = r"(?=さん|くん|君|ちゃん|ちゃ|っち|たん|氏|様|さま|先生|先輩|せんぱい)"
_tok = None


def _short_names(t):
    global _tok
    # 置き換えた文字列にまた名前が入っていても二重に置き換えないよう、いったん目印にする
    marks = {n: f"\x00{i}\x00" for i, n in enumerate(SHORT)}
    for n in SHORT:
        t = re.sub(re.escape(n) + HONORIFIC, marks[n], t)
    if any(n in t for n in SHORT):
        if _tok is None:
            from sudachipy import Dictionary
            _tok = Dictionary(dict="core").tokenizer()
        from sudachipy import SplitMode
        ms = list(_tok.tokenize(t, SplitMode.C))
        # 1 語に切れても「ゆう|がた」のような語の一部のことがあるので、
        # すぐあとが助詞・記号・文の終わりのときだけ名前とみなす（品詞は人名の判定が当てにならない）
        ends = lambda i: i + 1 == len(ms) or ms[i + 1].part_of_speech()[0] in ("助詞", "補助記号", "空白")
        t = "".join(marks[m.surface()] if m.surface() in marks and ends(i) else m.surface()
                    for i, m in enumerate(ms))
    for n, mark in marks.items():
        t = t.replace(mark, SHORT[n])
    return t


def to_plain(text):
    t = re.sub(r"https?://([^/\s]+)\S*", r"\1/…", text)
    t = re.sub(r"\((emoji|null)\)", "", t)
    for name, nick in _RENAME:
        if name.isascii():
            # ローマ字の名前は alice・SATO のように大文字と小文字が揺れる
            t = re.sub(r"(?<![A-Za-z])" + re.escape(name) + r"(?![A-Za-z])", nick, t, flags=re.I)
        else:
            t = t.replace(name, nick)
    for n, to in NICKNAMES:
        t = t.replace(n, to)
    return _short_names(t) if SHORT else t
