"""Sudachi（SplitMode C）で分かち書きし、内容語の原形を返す。"""
from functools import lru_cache

from sudachipy import Dictionary, SplitMode

from load import clean
from mask import name_parts
from person import CONFIG

_tok = Dictionary(dict="core").tokenizer()

# 数えても性格が出ない語
STOP = set("""
する いる ある なる れる られる できる 思う 言う いう 行く 来る くる 見る やる おる
こと もの ため よう それ これ あれ どれ そう こう 感じ 自分 今日 今 人 時 方 何 なん
ない いい よい 良い 無い さん ちゃん くん 的 系 中 前 後 上 下 気 一 二 三 回 日 月 年
とき ところ 先 否 あと 足 たしか せい いま 分 wd WD みたい っぽい やつ 一緒 全部 普通 ちょっと すごい 本当 ほんと まじ
""".split()) | set(CONFIG.get("extra_stopwords", []))
EN_STOP = set("""
a an the of in on at to for and or but is are was were be been this that it its with as by
from i you he she we they my your me do does did not no so if just can will
""".split())

# Sudachi が切ってしまう固有名詞は、先に取り出して 1 語として数える
COMPOUNDS = CONFIG.get("compounds", [])
# 人名と判定されないが人名の語（人の名前は数えない）。トークのメンバーの表示名とその一部も外す
_display = set(CONFIG.get("members", {})) | set(CONFIG.get("sender_aliases", {}))
NAMES = set(CONFIG.get("names", [])) | _display | {p for n in _display for p in name_parts(n)} \
    | set(CONFIG.get("members", {}).values()) | set(CONFIG.get("nicknames", []))

# 表記ゆれをそろえる（config.json の aliases。例: "github" → "GitHub"）
ALIASES = CONFIG.get("aliases", {})

KEEP_POS = {"名詞", "形容詞", "動詞", "形状詞", "感動詞"}


def is_paste(text):
    """ログなどを貼っただけのメッセージか。語の集計に入れると英単語が上位を占めてしまう。"""
    lines = [ln for ln in clean(text).splitlines() if ln.strip()]
    if len(lines) < 6:
        return False
    ascii_lines = sum(1 for ln in lines if sum(c.isascii() for c in ln) / len(ln) > 0.8)
    return ascii_lines / len(lines) > 0.5


@lru_cache(maxsize=None)
def tokens(text, pos=frozenset(KEEP_POS)):
    out = []
    if is_paste(text):
        return ()
    text = clean(text)
    for c in COMPOUNDS:
        if c in text:
            out += [ALIASES.get(c, c)] * text.count(c)
            text = text.replace(c, " ")
    for m in _tok.tokenize(text, SplitMode.C):
        p = m.part_of_speech()
        if p[0] not in pos or p[1] in {"数詞", "非自立可能"}:
            continue
        if p[2] == "人名":  # 人の名前は数えない
            continue
        w = m.normalized_form() if p[0] in {"動詞", "形容詞"} else m.surface()
        if len(w) < 2 and not ("一" <= w <= "龠"):
            continue
        if w in NAMES or w in STOP or w.lower() in EN_STOP or w.isdigit():
            continue
        out.append(ALIASES.get(w, w))
    return tuple(out)
