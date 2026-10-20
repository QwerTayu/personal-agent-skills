"""引用する本文の名前を伏せる。recap.json に書く前に使う。

- txt の表示名（config.json の members と sender_aliases のキー）とその一部は、members の呼び名に置き換える
- そのほかの名前（config.json の nicknames）は「〇〇」に置き換える。nicknames を {名前: 置き換える文字列} の形で書くと、
  メンバーの本名やあだ名を呼び名に置き換えられる
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
# 文字列の一部として置き換えるので、短い呼び名（「やま」など）は入れない。
# 短い名前は config.json の names に書き、語の集計からだけ外す
_nick = CONFIG.get("nicknames", [])
NICKNAMES = sorted((_nick.items() if isinstance(_nick, dict) else ((n, "〇〇") for n in _nick)),
                   key=lambda x: -len(x[0]))


def to_plain(text):
    t = re.sub(r"https?://([^/\s]+)\S*", r"\1/…", text)
    t = re.sub(r"\((emoji|null)\)", "", t)
    for name, nick in _RENAME:
        if name.isascii():
            t = re.sub(r"(?<![A-Za-z])" + re.escape(name) + r"(?![A-Za-z])", nick, t)
        else:
            t = t.replace(name, nick)
    for n, to in NICKNAMES:
        t = t.replace(n, to)
    return t
