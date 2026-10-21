"""やり取りの集計: 会話のまとまり・反応の速さ・通話・沈黙と連続・あいさつ・「ありがとう」・です・ます調。

人は load.py の key（p0 が本人）で表す。
"""
import collections
import re
import statistics
from datetime import timedelta

from load import CONFIG, ME, MODE

GAP_MIN = CONFIG.get("gap_hours", 3) * 60
THANKS_RE = re.compile(r"ありがと|感謝|助か|thx|thanks|thank you|サンキュ|あざ[すっま]", re.I)
POLITE_RE = re.compile(r"です|ます|ました|ません|でした|ましょう|ください")
QUESTION_RE = re.compile(r"[?？]")
GREETINGS = CONFIG.get("greetings") or {
    "おはよう": r"おは(?:よ|よう|ござ|ー|〜)|^おはー?$",
    "おやすみ": r"おやす|おやみ|^おや$",
}


def _minutes(a, b):
    return (b - a).total_seconds() / 60


def _median(xs):
    return round(statistics.median(xs), 1) if xs else None


def sessions(df):
    """前のメッセージから GAP_MIN 分あいたら、新しい会話とみなす。"""
    gap = df.dt.diff().dt.total_seconds().div(60)
    sid = (gap.isna() | (gap > GAP_MIN)).cumsum() - 1
    return df.assign(session=sid)


def talks(df):
    """会話のまとまり。だれが始め、だれが終えるか。いちばん長く続いた会話。"""
    g = df.groupby("session")
    starts, ends = g.who.first(), g.who.last()
    n = g.size()
    minutes = g.dt.agg(lambda s: _minutes(s.iloc[0], s.iloc[-1]))
    longest = int(n.idxmax())
    lg = df[df.session == longest]
    return dict(
        n=int(len(n)), gap_hours=GAP_MIN / 60,
        starters=dict(collections.Counter(starts)), enders=dict(collections.Counter(ends)),
        median_msgs=float(n.median()), median_minutes=round(float(minutes.median()), 1),
        longest=dict(start=lg.dt.iloc[0].isoformat(), end=lg.dt.iloc[-1].isoformat(), n=int(len(lg)),
                     minutes=round(_minutes(lg.dt.iloc[0], lg.dt.iloc[-1])), session=longest),
    )


def speed(df):
    """送り手が切り替わったところで、前の人のメッセージから返すまでの時間（会話の中だけ）。"""
    deltas = collections.defaultdict(list)
    by_hour = collections.defaultdict(lambda: collections.defaultdict(list))
    prev = None
    for r in df.itertuples():
        if prev is not None and r.session == prev.session and r.who != prev.who:
            d = _minutes(prev.dt, r.dt)
            deltas[r.who].append(d)
            by_hour[r.who][r.dt.hour].append(d)
        prev = r
    out = {}
    for k, ds in deltas.items():
        # 件数が少ない時間帯は中央値がぶれるので、10 件以上ある時間帯から選ぶ
        hours = {h: statistics.median(v) for h, v in by_hour[k].items() if len(v) >= 10}
        fastest = min(hours, key=hours.get) if hours else None
        within = lambda lim: round(sum(1 for d in ds if d <= lim) / len(ds), 3)
        out[k] = dict(median=_median(ds), n=len(ds), same_minute=within(0), within_5=within(5),
                      within_30=within(30), within_60=within(60),
                      fastest_hour=fastest, fastest_hour_median=round(hours[fastest], 1) if fastest is not None else None)
    return out


def calls(rows):
    """1 対 1 は Call time などの行、グループは開始と終了の時刻の差で数える。"""
    if not rows:
        return None
    if MODE == "pair":
        ans = [c for c in rows if c["status"] == "answered"]
        st = collections.Counter(c["status"] for c in rows)
        # 送り手はかけた側。Missed call は相手がかけて本人が出なかったもの
        tried = collections.Counter(c["who"] for c in rows if c["status"] in {"answered", "missed", "no_answer", "canceled"})
        longest = max(ans, key=lambda c: c["sec"]) if ans else None
        return dict(
            kind="pair", n=len(ans), total_min=round(sum(c["sec"] for c in ans) / 60),
            median_min=_median([c["sec"] / 60 for c in ans]),
            longest=dict(date=longest["dt"].isoformat(), min=round(longest["sec"] / 60), who=longest["who"]) if longest else None,
            callers=dict(collections.Counter(c["who"] for c in ans)), tried=dict(tried),
            missed=st["missed"], no_answer=st["no_answer"], canceled=st["canceled"],
            monthly=sorted(collections.Counter(c["dt"].strftime("%Y-%m") for c in ans).items()),
        )
    return None


def group_calls(rows, system):
    starts = sorted((c for c in rows if c["status"] == "group_start"), key=lambda c: c["dt"])
    ends = sorted(s["dt"] for s in system if s["event"] == "group_call_end")
    if not starts:
        return None
    durs = []
    for s in starts:
        e = next((e for e in ends if e >= s["dt"]), None)
        if e is not None:
            durs.append(dict(dt=s["dt"], min=round(_minutes(s["dt"], e)), who=s["who"]))
            ends.remove(e)
    longest = max(durs, key=lambda d: d["min"]) if durs else None
    return dict(kind="group", n=len(starts), total_min=sum(d["min"] for d in durs),
                longest=dict(date=longest["dt"].isoformat(), min=longest["min"], who=longest["who"]) if longest else None,
                callers=dict(collections.Counter(s["who"] for s in starts)))


def rhythm(df, span):
    """いちばん長い沈黙と、毎日やり取りした最長の連続日数。"""
    days = sorted(set(df.dt.dt.date))
    gap = max(((b - a).days - 1, a, b) for a, b in zip(days, days[1:])) if len(days) > 1 else (0, days[0], days[0])
    best, run, start, best_start = 1, 1, days[0], days[0]
    for a, b in zip(days, days[1:]):
        if b - a == timedelta(days=1):
            run += 1
        else:
            run, start = 1, b
        if run > best:
            best, best_start = run, start
    return dict(active_days=len(days), span_days=span,
                silence=dict(days=gap[0], after=gap[1].isoformat(), before=gap[2].isoformat()),
                streak=dict(days=best, start=best_start.isoformat(),
                            end=(best_start + timedelta(days=best - 1)).isoformat()))


def greetings(df):
    """あいさつを、だれが何回言ったか・その日に先に言ったのはだれか・何時ごろか。"""
    texts = df[df.is_text]
    out = []
    for label, pat in GREETINGS.items():
        hit = texts[texts.plain.str.contains(pat, regex=True)]
        if hit.empty:
            continue
        first = hit.groupby(hit.dt.dt.date).who.first()
        hours = {k: _median([d.hour + d.minute / 60 for d in g.dt]) for k, g in hit.groupby("who")}
        out.append(dict(label=label, n=dict(collections.Counter(hit.who)), first=dict(collections.Counter(first)),
                        days=int(first.size), hour=hours))
    return out


def thanks(df):
    t = df[df.is_text]
    return dict(collections.Counter(t[t.plain.str.contains(THANKS_RE)].who))


def polite(df, period_of, periods):
    """時期ごと・人ごとの、です・ます調と質問（？）の割合。20 件以上あるところだけ。"""
    t = df[df.is_text].assign(period=lambda x: x.dt.map(period_of))
    out = []
    for k, label, _ in periods:
        row = dict(key=k, label=label, people={})
        for who, g in t[t.period == k].groupby("who"):
            if len(g) >= 20:
                row["people"][who] = dict(polite=round(float(g.plain.str.contains(POLITE_RE).mean()), 3),
                                          question=round(float(g.plain.str.contains(QUESTION_RE).mean()), 3), n=int(len(g)))
        out.append(row)
    return out


def follows(df, top=8):
    """グループで、だれのあとにだれが書くことが多いか（会話の中で送り手が切り替わったところ）。"""
    c = collections.Counter()
    prev = None
    for r in df.itertuples():
        if prev is not None and r.session == prev.session and r.who != prev.who:
            c[(prev.who, r.who)] += 1
        prev = r
    return [dict(after=a, who=b, n=n) for (a, b), n in c.most_common(top)]


def unsent(system):
    return dict(collections.Counter(s["who"] for s in system if s["event"] == "unsent" and s["who"]))
