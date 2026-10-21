"""data/<slug>/recap.json と talks/<slug>/story.json をテンプレートに埋め込み、out/<slug>/ に単一 HTML を書く。"""
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


def main():
    for f in [DATA / "recap.json", STORY_PATH]:
        if not f.exists():
            sys.exit(f"{f} がない（recap.json は analyze.py で、story.json は手で作る）")
    recap = json.loads((DATA / "recap.json").read_text())
    story = json.loads(STORY_PATH.read_text())
    check(recap, story)
    pick_quotes(recap, story)
    payload = json.dumps(recap, ensure_ascii=False).replace("</", "<\\/")
    story_js = json.dumps(story, ensure_ascii=False).replace("</", "<\\/")
    OUT.mkdir(parents=True, exist_ok=True)
    for name in ["report.html", "wrapped.html"]:
        title = story["page_title"] if name == "report.html" else story["wrapped"]["page_title"]
        title = title.replace("&", "&amp;").replace("<", "&lt;")
        html = ((TEMPLATES / name).read_text().replace("/*__DATA__*/null", payload).replace("/*__STORY__*/null", story_js)
                .replace("__TITLE__", title))
        (OUT / name).write_text(html)
        print(f"wrote {OUT / name}")


if __name__ == "__main__":
    main()
