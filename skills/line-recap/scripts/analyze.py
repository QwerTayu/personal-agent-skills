#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.10"
# dependencies = ["sudachipy", "sudachidict-core", "scikit-learn", "pandas", "numpy"]
# ///
"""集計して data/recap.json を書く。作業場所で引数なしで実行する。HTML とスライドはこのファイルだけを読む。"""
import collections
import json
import sys

import numpy as np
from sklearn.decomposition import NMF
from sklearn.feature_extraction.text import TfidfVectorizer

import interact
from awards import awards
from load import CONFIG, EMOJI_RE, LINE_EMOJI_RE, MODE, PEOPLE, SINCE, UNTIL, load
from mask import to_plain
from person import DATA
from tokenize_ja import tokens

# 時期の区切りは月ごとの件数を見てトークごとに決める（config.json の periods）。
# 月は 4 のような数でも、"2026-04" のような年月でも書ける（年をまたぐ範囲は年月で書く）
PERIODS = [(k, label, tuple(str(m) for m in months)) for k, label, months in CONFIG["periods"]]
WEEKDAYS = "月火水木金土日"
N_TOPICS = CONFIG.get("n_topics", 8)
SHOW_TOPICS = CONFIG.get("show_topics", True)
MEDIA_KINDS = ["sticker", "photo", "video", "voice", "file", "location", "contact", "album", "other_media"]
NOUN_ADJ = frozenset({"名詞", "形容詞", "形状詞", "感動詞"})


def period_of(dt):
    for k, _, months in PERIODS:
        if dt.strftime("%Y-%m") in months or str(dt.month) in months:
            return k
    sys.exit(f"{dt:%Y-%m} のメッセージがどの時期（config.json の periods）にも入りません")


def fightin_words(counts_a, counts_b, prior=0.5, top=12):
    """Monroe ほか (2008) の log-odds（Dirichlet 事前分布つき）。a に特有の語を返す。
    prior が小さすぎる（0.05 など）と、b に 1 回も出ない語の分散が大きく見積もられ、a にしか出ない語ほど下に沈む。"""
    vocab = set(counts_a) | set(counts_b)
    na, nb = sum(counts_a.values()), sum(counts_b.values())
    a0 = prior * len(vocab)
    scores = {}
    for w in vocab:
        ya, yb = counts_a[w], counts_b[w]
        if ya < 2:
            continue
        la = np.log((ya + prior) / (na + a0 - ya - prior))
        lb = np.log((yb + prior) / (nb + a0 - yb - prior))
        var = 1 / (ya + prior) + 1 / (yb + prior)
        scores[w] = (la - lb) / np.sqrt(var)
    return [dict(word=w, z=round(float(z), 2), n=counts_a[w])
            for w, z in sorted(scores.items(), key=lambda x: (-round(x[1], 6), -counts_a[x[0]], x[0]))[:top]]


def span(df):
    first = SINCE or df.dt.min().date()
    last = UNTIL or df.dt.max().date()
    return first, last, (last - first).days + 1


def facts(df):
    by_day = df.groupby(df.dt.dt.date).size()
    best_day = by_day.idxmax()
    first, last, n_days = span(df)
    texts = df[df.is_text & ~df.link_only]
    per = {}
    for p in PEOPLE:
        mine = df[df.who == p["key"]]
        t = texts[texts.who == p["key"]]
        per[p["key"]] = dict(
            messages=int(len(mine)), share=round(len(mine) / len(df), 3),
            chars=int(t.plain.str.len().sum()), median_len=int(t.plain.str.len().median()) if len(t) else 0,
            links=int(mine.link_only.sum()),
            media={k: int((mine.kind == k).sum()) for k in MEDIA_KINDS if (mine.kind == k).any()},
        )
    return dict(
        messages=int(len(df)), texts=int(df.is_text.sum()),
        media={k: int((df.kind == k).sum()) for k in MEDIA_KINDS if (df.kind == k).any()},
        days=int(by_day.size), span_days=n_days, first=first.isoformat(), last=last.isoformat(),
        median_len=int(texts.plain.str.len().median()) if len(texts) else 0,
        best_day=dict(date=best_day.isoformat(), n=int(by_day.max()), weekday=WEEKDAYS[best_day.weekday()],
                      people={k: int(v) for k, v in df[df.dt.dt.date == best_day].who.value_counts().items()}),
        per_person=per,
    )


def when(df):
    monthly = df.groupby([df.dt.dt.strftime("%Y-%m"), "who"]).size().unstack(fill_value=0)
    heat = np.zeros((7, 24), dtype=int)
    for d in df.dt:
        heat[d.weekday(), d.hour] += 1
    hours = heat.sum(0)
    days = heat.sum(1)
    by_hour = {p["key"]: np.bincount(df[df.who == p["key"]].dt.dt.hour, minlength=24).tolist() for p in PEOPLE}
    night = list(range(21, 24)) + list(range(0, 3))
    share = lambda v, hs: round(sum(v[h] for h in hs) / sum(v), 3) if sum(v) else None
    return dict(
        monthly=[dict(month=m, n=int(r.sum()), people={k: int(v) for k, v in r.items() if v}) for m, r in monthly.iterrows()],
        heat=heat.tolist(),
        peak_hour=int(hours.argmax()),
        peak_weekday=WEEKDAYS[int(days.argmax())],
        by_weekday=days.tolist(),
        by_hour=hours.tolist(),
        by_hour_people=by_hour,
        peak_hour_people={k: int(np.argmax(v)) for k, v in by_hour.items() if sum(v)},
        night_share=round(float(heat[:, night].sum() / heat.sum()), 3),
        night_share_people={k: share(v, night) for k, v in by_hour.items()},
        morning_share_people={k: share(v, range(5, 10)) for k, v in by_hour.items()},
    )


def what(df):
    t = df[df.is_text].copy()
    t["period"] = t.dt.map(period_of)
    t["toks"] = t.text.map(tokens)
    # 時期の比較は名詞・形容詞だけで行う（動詞は「知る」「入れる」のような語が上に来てしまう）
    t["nouns"] = t.text.map(lambda x: tokens(x, NOUN_ADJ))
    counts = {k: collections.Counter(w for ws in t[t.period == k].nouns for w in ws) for k, _, _ in PERIODS}
    periods = []
    for k, label, months in PERIODS:
        rest = collections.Counter()
        for k2, c in counts.items():
            if k2 != k:
                rest.update(c)
        periods.append(dict(key=k, label=label, months=list(months), n=int((df.dt.map(period_of) == k).sum()),
                            words=fightin_words(counts[k], rest)))

    # 口ぐせ: 名詞・形容詞・形状詞・感動詞。全体と人ごと
    words = collections.Counter(w for ws in t.nouns for w in ws)
    people = {}
    for p in PEOPLE:
        mine = collections.Counter(w for ws in t[t.who == p["key"]].nouns for w in ws)
        rest = words - mine
        people[p["key"]] = dict(top=[dict(word=w, n=n) for w, n in mine.most_common(15)],
                                distinct=fightin_words(mine, rest, top=10))
    return dict(periods=periods, topics=topics_of(t) if SHOW_TOPICS else None,
                words=[dict(word=w, n=n) for w, n in words.most_common(40)], people=people)


def topics_of(t):
    """1 日分を 1 文書にまとめて TF-IDF + NMF。件数が少ないと寄せ集めになるので show_topics で切れる。"""
    days = t.groupby(t.dt.dt.date)
    docs = [" ".join(w for ws in g.toks for w in ws) for _, g in days]
    day_period = [period_of(g.dt.iloc[0]) for _, g in days]
    vec = TfidfVectorizer(tokenizer=str.split, token_pattern=None, lowercase=False, min_df=2, max_df=0.5)
    try:
        X = vec.fit_transform(docs)
    except ValueError:
        X = None
    n = min(N_TOPICS, *X.shape) if X is not None else 0
    if n < 2:
        print("トピック分類にはメッセージが少なすぎるので出さない（show_topics: false にするとよい）", file=sys.stderr)
        return None
    nmf = NMF(n_components=n, init="nndsvda", random_state=0, max_iter=1000)
    W = nmf.fit_transform(X)
    vocab = np.array(vec.get_feature_names_out())
    topics = []
    for i, comp in enumerate(nmf.components_):
        share = {}
        for k, _, _ in PERIODS:
            idx = [j for j, p in enumerate(day_period) if p == k]
            share[k] = round(float(W[idx, i].sum() / W[idx].sum()), 3) if idx and W[idx].sum() else 0
        topics.append(dict(id=i, words=vocab[comp.argsort()[::-1][:10]].tolist(),
                           weight=round(float(W[:, i].sum() / W.sum()), 3), share=share))
    return topics


# 記号は、ほとんどの人で言い回しより多く、言い回しの上位を占めてしまうので分けて数える
SYMBOLS = {
    "！": r"[!！]",
    "？": r"[?？]",
    "…": r"\.\.\.|…",
    "〜": r"[〜~]",
    "ーー": r"ー{2,}",  # 「すごーーい」のような伸ばし
    **CONFIG.get("symbols", {}),
}
EXPRESSIONS = {
    "草": r"草",
    "w": r"(?<![a-zA-Z])w{1,}(?![a-zA-Z])|ｗ+",
    "笑": r"笑",
    "ぴえん": r"ぴえん",
    "やばい": r"やば",
    "えぐい": r"えぐ",
    "おもろい": r"おもろ|面白",
    "好き": r"好き",
    "かわいい": r"かわい|可愛",
    **CONFIG.get("expressions", {}),
}


def habits(df):
    """人ごとの、言い回しと記号を含むメッセージの数と割合、本文の絵文字。"""
    t = df[df.is_text]
    out = {}
    for p in PEOPLE:
        mine = t[t.who == p["key"]]
        n = max(len(mine), 1)
        # URL やメンションの中の ? や w を数えないように、clean した本文で数える
        count = lambda pats: sorted(([k, int(c), round(int(c) / n, 3)] for k, pat in pats.items()
                                     for c in [mine.plain.str.contains(pat, regex=True).sum()]), key=lambda x: -x[1])
        emoji = collections.Counter(e for x in mine.text for e in EMOJI_RE.findall(x))
        line_emoji = sum(len(LINE_EMOJI_RE.findall(x)) for x in mine.text)
        out[p["key"]] = dict(
            expressions=count(EXPRESSIONS), symbols=count(SYMBOLS),
            emoji=[dict(char=e, n=c) for e, c in emoji.most_common(8)], line_emoji=line_emoji,
        )
    return out


def _quote(r):
    if r.kind != "text":
        label = {"sticker": "［スタンプ］", "photo": "［写真］", "video": "［動画］", "voice": "［ボイスメッセージ］",
                 "file": "［ファイル］", "location": "［位置情報］", "contact": "［連絡先］", "album": "［アルバム］"}.get(r.kind, "［そのほか］")
        return dict(date=r.dt.strftime("%Y-%m-%d %H:%M"), who=r.who, text=label, media=True)
    return dict(date=r.dt.strftime("%Y-%m-%d %H:%M"), who=r.who, text=to_plain(r.text))


def period_quotes(t, periods):
    """時期ごとに、引用の候補を最大 8 件（物語の版のスライドで使う。story.json の wrapped.chapter_quotes で選ぶ）。
    config.json の period_quote_words に書いた語を含むものを先に、次にその時期の特徴語を含むものを選ぶ。"""
    extra = CONFIG.get("period_quote_words", {})
    out = {}
    for p in periods:
        words = [w["word"] for w in p["words"][:5]]
        prefer = extra.get(p["key"], [])
        mine = t[t.dt.map(period_of) == p["key"]]
        mine = mine[mine.plain.str.len().between(6, 60)]
        score = mine.plain.map(lambda x: 10 * sum(w in x for w in prefer) + sum(w in x for w in words))
        pick = mine.assign(score=score)[score > 0].sort_values(["score", "dt"], ascending=[False, True]).head(8)
        out[p["key"]] = [_quote(r) for r in pick.sort_values(["dt", "seq"]).itertuples()]
    return out


def streak_detail(df, streak):
    """毎日話した最長の期間に、何を話していたか。ほかの日と比べた特徴語と、それを含む引用の候補（最大 8 件）。"""
    t = df[df.is_text & ~df.link_only]
    d = t.dt.dt.date.map(lambda x: x.isoformat())
    inside = t[(d >= streak["start"]) & (d <= streak["end"])]
    outside = t.drop(inside.index)
    count = lambda x: collections.Counter(w for txt in x.text for w in tokens(txt, NOUN_ADJ))
    words = fightin_words(count(inside), count(outside), top=8)
    top = [w["word"] for w in words[:5]]
    cand = inside[inside.plain.str.len().between(6, 60)]
    score = cand.plain.map(lambda x: sum(w in x for w in top))
    pick = cand.assign(score=score)[score > 0].sort_values(["score", "dt"], ascending=[False, True]).head(8)
    return dict(messages=int((df.dt.dt.date.map(lambda x: x.isoformat()).between(streak["start"], streak["end"])).sum()),
                words=words, quotes=[_quote(r) for r in pick.sort_values(["dt", "seq"]).itertuples()])


def highlights(df, best_day, longest_session, periods):
    """引用は全員の発言から選ぶ（ユーザーが決めた）。名前は recap.json に書く前に伏せる。
    ページで使うものだけを書く（使わない引用まで HTML に埋め込まないため）。"""
    t = df[df.is_text & ~df.link_only]
    on_best = t[t.dt.dt.date.map(lambda d: d.isoformat()) == best_day]
    # いちばん書いた日の、長めのメッセージを時刻の順に
    best = on_best.loc[on_best.plain.str.len().nlargest(4).index].sort_values(["dt", "seq"])
    lg = df[df.session == longest_session].head(8)
    return dict(
        first=[_quote(r) for r in df.head(4).itertuples()],
        best_day=[_quote(r) for r in best.itertuples()],
        longest_talk=[_quote(r) for r in lg.itertuples()],
        longest_text=[_quote(r) for r in t.loc[t.plain.str.len().nlargest(1).index].itertuples()],
        periods=period_quotes(t, periods),
    )


def main():
    df, call_rows, system, dropped = load()
    df = interact.sessions(df)
    f = facts(df)
    talks = interact.talks(df)
    wt = what(df)
    recap = dict(
        talk=dict(title=CONFIG.get("title") or "トーク", mode=MODE),
        people=PEOPLE,
        facts=f,
        when=when(df),
        what=wt,
        habits=habits(df),
        talks=talks,
        speed=interact.speed(df),
        calls=interact.calls(call_rows) if MODE == "pair" else interact.group_calls(call_rows, system),
        rhythm=interact.rhythm(df, f["span_days"]),
        greetings=interact.greetings(df),
        thanks=interact.thanks(df),
        unsent=interact.unsent(system),
        polite=interact.polite(df, period_of, PERIODS),
        follows=interact.follows(df) if MODE == "group" else None,
        highlights=highlights(df, f["best_day"]["date"], talks["longest"]["session"], wt["periods"]),
        dropped=dropped,
    )
    for p in recap["people"]:
        p["n"] = f["per_person"][p["key"]]["messages"]
    recap["rhythm"]["streak"].update(streak_detail(df, recap["rhythm"]["streak"]))
    recap["awards"] = awards(recap)
    DATA.mkdir(parents=True, exist_ok=True)
    out = DATA / "recap.json"
    out.write_text(json.dumps(recap, ensure_ascii=False, indent=1, default=str))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
