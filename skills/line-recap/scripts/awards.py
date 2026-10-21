"""スライドの表彰式で使う、人ごとの称号の候補を集計結果から選ぶ。

指標ごとに「その人がほかの人よりどれだけ目立つか」を点にし、点の高い順に、1 人 1 つ・同じ称号は 1 回だけ割り当てる。
称号と説明は story.json の wrapped.awards で上書きできる（テンプレートが上書きする）。
"""


def _rate_scores(values):
    """割合の指標。全員の平均の何倍か。"""
    vals = {k: v for k, v in values.items() if v is not None}
    if len(vals) < 2:
        return {}
    mean = sum(vals.values()) / len(vals)
    return {k: v / mean for k, v in vals.items() if mean > 0 and v > 0}


def _count_scores(values, min_n=3, prior=2):
    """回数の指標。人数で割った公平な取り分の何倍か。
    回数が少ないと割合が極端になる（5 回中 4 回など）ので、全員に prior 回ずつ足してならす。"""
    total = sum(values.values())
    if total < min_n or len(values) < 2:
        return {}
    n = len(values)
    return {k: (v + prior) / (total + prior * n) * n for k, v in values.items() if v >= min_n}


def candidates(r):
    """(称号, 絵文字, 点の dict, 数字の書き方) の一覧。"""
    keys = [p["key"] for p in r["people"]]
    per = r["facts"]["per_person"]
    sp = r["speed"]
    hab = r["habits"]
    sym = lambda k, s: next((e[2] for e in hab[k]["symbols"] if e[0] == s), 0)
    msgs = {k: per[k]["messages"] for k in keys}
    enough = {k for k in keys if msgs[k] >= 30}  # 割合は 30 件以上ある人だけで比べる
    greet = {g["label"]: g["first"] for g in r["greetings"]}
    polite = {}
    for k in keys:
        rows = [(p["people"][k]["polite"], p["people"][k]["n"]) for p in r["polite"] if k in p["people"]]
        n = sum(x for _, x in rows)
        polite[k] = sum(v * x for v, x in rows) / n if n else None
    out = [
        ("いちばん話す人", "💬", _count_scores(msgs), lambda k: f"{msgs[k]:,}件"),
        ("スタンプ王", "🧸", _count_scores({k: per[k]["media"].get("sticker", 0) for k in keys}),
         lambda k: f"スタンプ{per[k]['media'].get('sticker', 0)}個"),
        ("写真係", "📷", _count_scores({k: per[k]["media"].get("photo", 0) for k in keys}),
         lambda k: f"写真{per[k]['media'].get('photo', 0)}枚"),
        ("会話の口火を切る人", "🔥", _count_scores({k: r["talks"]["starters"].get(k, 0) for k in keys}),
         lambda k: f"会話を始めた回数 {r['talks']['starters'].get(k, 0)}回"),
        ("会話を締める人", "🔚", _count_scores({k: r["talks"]["enders"].get(k, 0) for k in keys}),
         lambda k: f"最後に書いた回数 {r['talks']['enders'].get(k, 0)}回"),
        ("即レス王", "⚡", _rate_scores({k: sp[k]["same_minute"] for k in keys if k in sp and sp[k]["n"] >= 30}),
         lambda k: f"即レス率 {round(sp[k]['same_minute'] * 100)}%"),
        ("夜ふかし", "🦉", _rate_scores({k: r["when"]["night_share_people"].get(k) for k in enough}),
         lambda k: f"21〜3時が{round(r['when']['night_share_people'][k] * 100)}%"),
        ("朝型", "☀️", _rate_scores({k: r["when"]["morning_share_people"].get(k) for k in enough}),
         lambda k: f"5〜9時が{round(r['when']['morning_share_people'][k] * 100)}%"),
        ("長文の人", "📜", _rate_scores({k: per[k]["median_len"] for k in enough}),
         lambda k: f"1通 {per[k]['median_len']}字"),
        ("質問の人", "❓", _rate_scores({k: sym(k, "？") for k in enough}), lambda k: f"「？」が{round(sym(k, '？') * 100)}%"),
        ("！の人", "❗", _rate_scores({k: sym(k, "！") for k in enough}), lambda k: f"「！」が{round(sym(k, '！') * 100)}%"),
        ("敬語の人", "🎩", _rate_scores({k: polite[k] for k in enough if polite[k]}),
         lambda k: f"です・ます {round(polite[k] * 100)}%"),
        ("ありがとうの人", "🙏", _count_scores({k: r["thanks"].get(k, 0) for k in keys}),
         lambda k: f"ありがとう {r['thanks'].get(k, 0)}回"),
        ("取り消しの人", "↩️", _count_scores({k: r["unsent"].get(k, 0) for k in keys}, min_n=2),
         lambda k: f"送信取り消し {r['unsent'].get(k, 0)}回"),
    ]
    for label, first in greet.items():
        out.append((f"{label}担当", "☀️" if "おは" in label else "🌙", _count_scores({k: first.get(k, 0) for k in keys}),
                    lambda k, first=first, label=label: f"先に「{label}」{first.get(k, 0)}日"))
    # 口ぐせ: その人のいちばん割合の高い言い回しが、ほかの人の平均の何倍か
    for k in enough:
        e = max(hab[k]["expressions"], key=lambda x: x[2], default=None)
        if not e or e[1] < 3:
            continue
        others = [next((x[2] for x in hab[o]["expressions"] if x[0] == e[0]), 0) for o in enough if o != k]
        mean = sum(others) / len(others) if others else 0
        score = e[2] / mean if mean else 3.0
        out.append((f"「{e[0]}」の人", "🗣️", {k: score}, lambda k, e=e: f"「{e[0]}」{e[1]}回"))
    return out


def awards(r):
    picks, used_title, used_person = [], set(), set()
    rows = sorted(((score, title, emoji, k, stat) for title, emoji, scores, stat in candidates(r)
                   for k, score in scores.items()), key=lambda x: -x[0])
    for score, title, emoji, k, stat in rows:
        if k in used_person or title in used_title or score < 1.05:
            continue
        picks.append(dict(key=k, title=title, emoji=emoji, stat=stat(k), score=round(score, 2)))
        used_person.add(k)
        used_title.add(title)
    order = {p["key"]: i for i, p in enumerate(r["people"])}
    return sorted(picks, key=lambda a: order[a["key"]])
