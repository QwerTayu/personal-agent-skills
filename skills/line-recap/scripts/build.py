"""data/recap.json と story.json をテンプレートに埋め込み、out/ に単一 HTML を書く。作業場所で引数なしで実行する。"""
import json
import sys

from person import DATA, OUT, SKILL_DIR, STORY_PATH

TEMPLATES = SKILL_DIR / "templates"


def check(recap, story):
    """story.json と recap.json が食い違っていたら、どこが違うかを書いて止める。
    テンプレートの JS は途中で落ちるとページが白くなり、原因が分かりにくいため。"""
    errs = []
    sw = story.get("wrapped", {})
    for k in ["page_title", "title", "lede", "what_heading", "periods"]:
        if k not in story:
            errs.append(f"story.json に {k} がない")
    for k in ["page_title", "intro_title"]:
        if k not in sw:
            errs.append(f"story.json の wrapped に {k} がない")
    keys = [p["key"] for p in recap["what"]["periods"]]
    missing = [k for k in keys if k not in story.get("periods", {})]
    if missing:
        errs.append(f"story.json の periods に {missing} がない（config.json の periods のキーと合わせる）")
    q = sw.get("best_day_quote")
    if q is not None and not (0 <= q < len(recap["highlights"]["best_day"])):
        errs.append(f"wrapped.best_day_quote={q} は highlights.best_day（{len(recap['highlights']['best_day'])} 件）の範囲外")
    for k, idx in sw.get("chapter_quotes", {}).items():
        n = len(recap["highlights"].get("periods", {}).get(k, []))
        bad = [i for i in idx if not 0 <= i < n]
        if bad:
            errs.append(f"wrapped.chapter_quotes.{k} の {bad} は候補（{n} 件）の範囲外")
    n = len(recap["rhythm"]["streak"].get("quotes", []))
    bad = [i for i in sw.get("streak_quotes", []) if not 0 <= i < n]
    if bad:
        errs.append(f"wrapped.streak_quotes の {bad} は候補（{n} 件）の範囲外")
    people = {p["name"] for p in recap["people"]}
    unknown_aw = [n for n in sw.get("awards", {}) if n not in people]
    if unknown_aw:
        errs.append(f"wrapped.awards の {unknown_aw} がメンバーの呼び名にない（{sorted(people)} から選ぶ）")
    names = {e[0] for h in recap["habits"].values() for e in h["expressions"]}
    unknown = [k for k in sw.get("habits_keys", []) if k not in names]
    if unknown:
        errs.append(f"wrapped.habits_keys の {unknown} が言い回しにない（{sorted(names)} から選ぶ）")
    if errs:
        sys.exit("\n".join(errs))


def pick_quotes(recap, story):
    """引用の候補のうち、ページで使うものだけを残す（使わない候補まで HTML に埋め込まないため）。
    章の吹き出しは wrapped.chapter_quotes、毎日話した最長の吹き出しは wrapped.streak_quotes で選ぶ。省くと最初の 3 件"""
    sw = story.setdefault("wrapped", {})
    choose = lambda items, idx: [items[i] for i in idx] if idx is not None else items[:3]
    periods = recap["highlights"].get("periods", {})
    for k in list(periods):
        periods[k] = choose(periods[k], sw.get("chapter_quotes", {}).get(k))
    streak = recap["rhythm"]["streak"]
    streak["quotes"] = choose(streak.get("quotes", []), sw.get("streak_quotes"))
    sw.pop("chapter_quotes", None)
    sw.pop("streak_quotes", None)


# テンプレートが story.json から読む項目（templates/*.html の S.<項目>、wrapped の下は SW.<項目>）。
# 表示しない項目（スライドの next、書き足したメモなど）まで HTML のソースに残さないよう、これだけを埋め込む。
# 下の階層（periods・wrapped・wrapped.awards の中）も同じように絞る。
# テンプレートで新しい項目を読むときは、ここにも足す。page_title は <title> に入れるので JS には渡さない
REPORT_KEYS = ["calls_body", "calls_heading", "facts_heading", "facts_note", "follows_heading", "greetings_heading",
               "habits_heading", "highlights_heading", "lede", "longest_talk_body", "next", "people_words_heading",
               "periods", "polite_body", "polite_heading", "rhythm_body", "rhythm_heading", "show_longest_text",
               "speed_body", "speed_heading", "talks_body", "talks_heading", "title", "topics", "topics_note",
               "what_heading", "when_body", "when_heading", "words_body", "words_heading"]
WRAPPED_KEYS = ["periods", "what_heading", "wrapped"]
SLIDE_KEYS = ["awards", "awards_heading", "battle_body", "battle_heading", "best_day_body", "best_day_quote", "card_body",
              "card_heading", "first_heading", "habits_body", "habits_heading", "habits_keys", "hour_body", "hour_heading",
              "intro_title", "longest_talk_body", "longest_talk_heading", "messages_body", "messages_kicker",
              "overall_heading", "periods_kicker", "rhythm_body", "share_heading", "speed_body", "speed_heading",
              "talks_body", "talks_heading", "top_word_body"]
PERIOD_KEYS = ["title", "body"]
AWARD_KEYS = ["title", "body", "emoji"]


def pick(d, keys):
    return {k: d[k] for k in keys if k in d} if isinstance(d, dict) else d


def story_for(name, story):
    """そのテンプレートが使う story の項目だけを返す"""
    out = pick(story, WRAPPED_KEYS if name == "wrapped.html" else REPORT_KEYS)
    if isinstance(out.get("periods"), dict):
        out["periods"] = {k: pick(v, PERIOD_KEYS) for k, v in out["periods"].items()}
    if "wrapped" in out:
        out["wrapped"] = pick(out["wrapped"], SLIDE_KEYS)
        if isinstance(out["wrapped"].get("awards"), dict):
            out["wrapped"]["awards"] = {n: pick(a, AWARD_KEYS) for n, a in out["wrapped"]["awards"].items()}
    return out


def main():
    for f in [DATA / "recap.json", STORY_PATH]:
        if not f.exists():
            sys.exit(f"{f} がない（recap.json は analyze.py で、story.json は手で作る）")
    recap = json.loads((DATA / "recap.json").read_text())
    story = json.loads(STORY_PATH.read_text())
    check(recap, story)
    pick_quotes(recap, story)
    payload = json.dumps(recap, ensure_ascii=False).replace("</", "<\\/")
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ["report.html", "wrapped.html"]:
        story_js = json.dumps(story_for(name, story), ensure_ascii=False).replace("</", "<\\/")
        title = story["page_title"] if name == "report.html" else story["wrapped"]["page_title"]
        title = title.replace("&", "&amp;").replace("<", "&lt;")
        html = ((TEMPLATES / name).read_text().replace("/*__DATA__*/null", payload).replace("/*__STORY__*/null", story_js)
                .replace("__TITLE__", title))
        (OUT / name).write_text(html)
        print(f"wrote {OUT / name}")


if __name__ == "__main__":
    main()
