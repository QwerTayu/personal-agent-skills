#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["sudachipy", "sudachidict-core", "pandas"]
# ///
"""人の名前を洗い出す。config.json の names / nicknames を決めるために使う。

Usage: uv run <skill>/scripts/find_names.py <slug>

1. Sudachi が人名と判定した語（トークにいない人や、メンバーの本名・あだ名）
2. メンバーの表示名とその一部のうち、本文に出てくるもの（引用では自動で呼び名に置き換わる）
3. data/<slug>/recap.json と out/<slug>/*.html に残っているもの
4. 1 のうち、ページでの表示をまだユーザーに聞いていないもの（nicknames にないもの）
を表示する。1 には普通の語（「そう」「はな」など）も混ざるので、目で見て選ぶ。
"""
import collections
import re

from sudachipy import Dictionary, SplitMode

from load import KEY_OF, load
from mask import name_parts
from person import CONFIG, DATA, OUT

df, _, _, _ = load()
texts = df[df.is_text].text

print("== 1. Sudachi が人名と判定した語（回数）")
tok = Dictionary(dict="core").tokenizer()
pn = collections.Counter(m.surface() for t in texts for m in tok.tokenize(t, SplitMode.C)
                         if m.part_of_speech()[2] == "人名")
print(pn.most_common(60))

print("== 2. 本文に出てくるメンバーの表示名とその一部（回数。引用では呼び名に置き換わる）")
display = set(KEY_OF) | set(CONFIG.get("sender_aliases", {}))
# 呼び名と同じ文字列は、ページに出してよい
parts = {p for n in display for p in name_parts(n) | {n}} - set(CONFIG.get("members", {}).values())
joined = "\n".join(texts)
print({p: joined.count(p) for p in sorted(parts, key=len, reverse=True) if p in joined})

print("== 3. 出力に残っているもの")
nick = CONFIG.get("nicknames", [])
names = CONFIG.get("names", [])
for f in [DATA / "recap.json", *sorted(OUT.glob("*.html"))]:
    if not f.exists():
        continue
    s = f.read_text()
    # 表示をそのままにすると答えた名前（{"太郎": "太郎"}）は、残っていてよい
    left = {n: s.count(n) for n in nick if n in s and not (isinstance(nick, dict) and nick[n] == n)}
    # 英字の候補は、HTML の JS（client など）の一部に当たらないよう、単語として探す。
    # mask.py と同じく、大文字と小文字は区別しない
    found = lambda n: (len(re.findall(r"(?<![A-Za-z])" + re.escape(n) + r"(?![A-Za-z])", s, flags=re.I))
                       if n.isascii() else s.count(n))
    shown = {p: found(p) for p in parts if found(p)}
    short = {n: s.count(n) for n in names if n not in nick and n in s}
    guess = {n: found(n) for n, _ in pn.most_common(60) if len(n) >= 2 and n not in names and n not in nick and found(n)}
    print(f"{f}:\n  表示名とその一部（出てはいけない）={shown}\n  nicknames（出てはいけない）={left}\n"
          f"  names（nicknames にないので置き換えていない。引用に出ていないか目で見る）={short}\n"
          f"  1 の候補で出力にあるもの（names / nicknames に入れるか決める）={guess}")

print("== 4. 表示をまだ聞いていない人名の候補（1 から、nicknames に書いたものとメンバーの名前を除いた。普通の語は目で外す）")
asked = set(nick) | parts | set(CONFIG.get("members", {}).values()) | set(display)
print([n for n, _ in pn.most_common(60) if n not in asked])
