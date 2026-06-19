"""Cloud daily updater (GitHub Actions). Scrape one day of People's Daily, score it with the
exact prompts (DeepSeek) + jieba lexicon/LSS, and update scores_{daily,weekly,monthly}.csv.
Weekly/monthly are n_art-weighted means of daily => exactly reproduce per-article aggregation.

Env: DEEPSEEK_API_KEY.  Usage: python pipeline/daily_update.py [YYYY-MM-DD]  (default: yesterday UTC)
Article TEXT is never written out — only aggregate country-period scores.
"""
import os, re, sys, json, time, html, urllib.request
from datetime import date, timedelta, timezone, datetime
from concurrent.futures import ThreadPoolExecutor
import pandas as pd, jieba

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from scrape_pd import day_rows, fetch_one            # reuse the validated scraper

KEY = os.environ["DEEPSEEK_API_KEY"]
EP = "https://api.deepseek.com/chat/completions"
FLASH = PRO = "deepseek-v4-pro"   # run ALL DeepSeek calls on Pro (summary/classify/frame/threat/translate)
WORKERS = 10

# all-country actor->key map (12 majors keep friendly keys; others use full names), from the
# C1 mapping shipped in the repo (actor_to_country.csv). Falls back to the 12 if the file is absent.
_ISO2FRIENDLY = {"USA":"US","GBR":"UK","RUS":"Russia","KOR":"South Korea","JPN":"Japan","FRA":"France",
                 "IND":"India","DEU":"Germany","VNM":"Vietnam","AUS":"Australia","IDN":"Indonesia","PAK":"Pakistan"}
_MAP = os.path.join(REPO, "actor_to_country.csv")
if os.path.exists(_MAP):
    _m = pd.read_csv(_MAP, encoding="utf-8-sig"); _m = _m[_m["action"] == "map"]
    LAB2C = {r["actor"]: _ISO2FRIENDLY.get(r["iso3"], r["country"]) for _, r in _m.iterrows()}
else:
    LAB2C = {"United States":"US","Soviet Union":"Russia","Russia":"Russia","Japan":"Japan",
             "United Kingdom":"UK","Britain":"UK","England":"UK","France":"France","India":"India",
             "Germany":"Germany","West Germany":"Germany","East Germany":"Germany","Vietnam":"Vietnam",
             "North Vietnam":"Vietnam","South Vietnam":"Vietnam","South Korea":"South Korea",
             "Australia":"Australia","Indonesia":"Indonesia","Pakistan":"Pakistan"}
GRP = sorted(set(LAB2C.values()))   # country keys for the 0-filled daily grid
FRAMES = ["law_deg","norms_deg","threat_deg","selfdef_deg","limited_deg","discr_deg"]
MEAS = ["deepseek","lexicon","lss","negativity"] + FRAMES

def read_sys(fn):
    L = open(os.path.join(HERE, fn), encoding="utf-8").read().splitlines()
    i_s = next(i for i,l in enumerate(L) if "系统提示" in l)
    i_u = next(i for i,l in enumerate(L) if "用户提示" in l)
    return "\n".join(L[i_s+1:i_u])
CLASSIFY_SYS = read_sys("article_classify_prompt.txt")
FRAME_SYS = read_sys("article_frame_prompt.txt")
SUMMARY_SYS = ("你是《人民日报》文章摘要员。请用中文客观概括下文的主要内容，150–250字，"
               "只陈述事实与文章基调，不评论、不添加外部信息。只输出摘要正文。")
THREAT_SYS = ("你是一位资深的中国对外关系研究专家，专长于中国大陆官方媒体话语分析。\n"
 "【核心定义】\"隐性威胁\"操作化为：报道所体现的发话方（中国大陆官方/官媒）在未来数日内对相关外部行为体诉诸武力的可能性。\n"
 "【识别线索（隐性威胁惯用语）】严重后果、一切后果、后果、恶果、消极影响、负面影响、不良后果、适得其反、恶劣影响、"
 "后果严重、自食恶果、自食其果、不顾后果、玩火自焚、自取灭亡、引火自焚、自寻死路、苦果、玩火。\n"
 "【任务】阅读摘要，输出 JSON：{\"sentiment\":<0-1两位小数,未来数日诉诸武力可能性>,\"confidence\":<0-100>,\"rationale\":\"<不超过20字>\"}，仅返回JSON。")

jieba.load_userdict(os.path.join(HERE, "user.dict.utf8.txt"))
IT19 = [w.strip() for w in open(os.path.join(HERE,"lexicon_psrm19.txt"),encoding="utf-8") if w.strip()]
BETA = {k: float(v) for k, v in json.load(open(os.path.join(HERE,"lss_beta.json"),encoding="utf-8")).items()}

def call_ds(model, sysmsg, user, json_mode=True, tries=4):
    body = {"model": model, "temperature": 0,
            "messages": [{"role":"system","content":sysmsg},{"role":"user","content":user}]}
    if json_mode: body["response_format"] = {"type":"json_object"}
    data = json.dumps(body).encode()
    for a in range(tries):
        try:
            req = urllib.request.Request(EP, data=data, method="POST",
                headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"})
            with urllib.request.urlopen(req, timeout=180) as r:
                ct = json.loads(r.read())["choices"][0]["message"]["content"]
            return json.loads(ct) if json_mode else ct.strip()
        except Exception:
            time.sleep(2*(a+1))
    return None

def num(x):
    try: return float(x)
    except (TypeError, ValueError): return None

def lex_lss(content):
    toks = [t for t in jieba.cut(content or "") if t.strip()]
    if not toks: return 0.0, 0.0
    it = sum(1 for t in toks if t in IT19)/len(toks)
    w = [BETA[t] for t in toks if t in BETA]
    return round(it,8), round(sum(w)/len(w) if w else 0.0, 6)

def score(art):
    summ = call_ds(FLASH, SUMMARY_SYS, f"标题：{art['title']}\n正文：{art['content'][:6000]}", json_mode=False) or ""
    cls = call_ds(FLASH, CLASSIFY_SYS, f"标题：{art['title']}\n摘要：{summ}\n\n请按系统提示中的定义判断并输出 JSON。") or {}
    cov = cls.get("涉外", {}) or {}
    is_fc = bool(cov.get("是否涉外")) and bool(cov.get("涉及中国"))
    frm = call_ds(FLASH, FRAME_SYS, f"标题：{art['title']}\n摘要：{summ}\n\n请按系统提示中的定义判断并输出 JSON。") if is_fc else None
    thr = call_ds(PRO, THREAT_SYS, "请对以下报道摘要进行威胁性打分。\n\n"+summ) if is_fc else None
    it_lex, it_lss = lex_lss(art["content"])
    fr = (frm or {}).get("各框架", {}) or {}
    fd = lambda k: num((fr.get(k) or {}).get("程度"))
    return {"date":art["date"], "title":art.get("title",""), "url":art.get("url",""),
            "summary":(summ or "")[:300],
            "main_foreign_actors":"; ".join(cls.get("主要外国行为体",[]) or []),
            "foreign":is_fc, "negativity":num((cls.get("情感") or {}).get("负面度")),
            "deepseek":num((thr or {}).get("sentiment")), "lexicon":it_lex, "lss":it_lss,
            "law_deg":fd("law"),"norms_deg":fd("norms"),"threat_deg":fd("threat"),
            "selfdef_deg":fd("selfdef"),"limited_deg":fd("limited"),"discr_deg":fd("discrimination")}

def country_day_rows(scored, dstr):
    rows = []
    for r in scored:
        for actor in [a.strip() for a in (r["main_foreign_actors"] or "").split(";")]:
            if actor in LAB2C:
                rr = dict(r); rr["country"] = LAB2C[actor]; rows.append(rr)
    df = pd.DataFrame(rows)
    out = []
    for c in GRP:
        g = df[df["country"]==c] if len(df) else df
        rec = {"country":c, "period":dstr, "n_art":int(len(g))}
        for m in MEAS:
            rec[m] = float(g[m].mean()) if len(g) and g[m].notna().any() else 0.0
        out.append(rec)
    return pd.DataFrame(out)

TRANSLATE_SYS = ("You translate Chinese newspaper headlines into concise, natural English. "
                 "Input is a JSON array of headlines. Output JSON {\"t\": [\"en1\", \"en2\", ...]} with "
                 "exactly one English translation per input headline, in the same order. Keep any "
                 "parenthetical column name translated too. Output JSON only.")

def translate_titles(titles):
    """Batch-translate a list of Chinese headlines to English via DeepSeek. Returns a same-length list
    (empty strings on failure, so the Chinese still shows)."""
    if not titles:
        return []
    out = call_ds(FLASH, TRANSLATE_SYS, json.dumps(titles, ensure_ascii=False))
    en = (out or {}).get("t") if isinstance(out, dict) else None
    if isinstance(en, list) and len(en) == len(titles):
        return [str(x) for x in en]
    return [""] * len(titles)

def update_recent_titles(scored, dstr, n=2):
    """Keep recent_titles.csv (country -> n most-recent headlines + links, Chinese + English) current for
    the map hover. Only headline + URL are stored, never article body text."""
    tpath = os.path.join(REPO, "recent_titles.csv")
    new = []
    for r in scored:
        if not r.get("title"):
            continue
        for actor in [a.strip() for a in (r.get("main_foreign_actors") or "").split(";")]:
            if actor in LAB2C:
                new.append({"country": LAB2C[actor], "date": dstr, "title": r["title"],
                            "title_en": "", "url": r.get("url", "")})
    new = pd.DataFrame(new, columns=["country", "date", "title", "title_en", "url"])
    if new.empty:
        return
    old = pd.read_csv(tpath, encoding="utf-8-sig") if os.path.exists(tpath) else \
        pd.DataFrame(columns=["country", "date", "title", "title_en", "url"])
    if "title_en" not in old.columns:
        old["title_en"] = ""
    old = old[old["date"] != dstr]                                  # idempotent: replace this date
    both = pd.concat([new, old], ignore_index=True)                 # new (this date) first => wins ties
    both = both.sort_values("date", ascending=False, kind="stable")
    both = both.groupby("country", as_index=False, sort=False).head(n).reset_index(drop=True)

    # translate only the surviving headlines that still lack English
    both["title_en"] = both["title_en"].fillna("")
    need = both.index[both["title_en"].str.strip() == ""].tolist()
    if need:
        en = translate_titles(both.loc[need, "title"].tolist())
        for i, e in zip(need, en):
            both.at[i, "title_en"] = e
    both = both[["country", "date", "title", "title_en", "url"]]
    both.to_csv(tpath, index=False)
    print(f"[daily] refreshed recent_titles.csv ({both['country'].nunique()} countries, "
          f"{len(need)} translated)", flush=True)

def update_negative_titles(scored, dstr, n=1, window_days=7):
    """Keep negative_titles.csv (country -> THE single most-NEGATIVE article within the last
    `window_days`, with a short summary) current for the map hover. Rolling window; headline +
    URL + sentiment + a clipped summary stored, never full article text."""
    npath = os.path.join(REPO, "negative_titles.csv")
    cols = ["country", "date", "title", "title_en", "url", "sentiment", "summary", "summary_en"]
    new = []
    for r in scored:
        if not r.get("title") or r.get("negativity") is None:
            continue
        summ = (r.get("summary") or "").replace("\n", " ")[:120]
        for actor in [a.strip() for a in (r.get("main_foreign_actors") or "").split(";")]:
            if actor in LAB2C:
                new.append({"country": LAB2C[actor], "date": dstr, "title": r["title"], "title_en": "",
                            "url": r.get("url", ""), "sentiment": float(r["negativity"]),
                            "summary": summ, "summary_en": ""})
    new = pd.DataFrame(new, columns=cols)
    old = pd.read_csv(npath, encoding="utf-8-sig") if os.path.exists(npath) else pd.DataFrame(columns=cols)
    for c in cols:
        if c not in old.columns:
            old[c] = "" if c in ("title_en", "summary", "summary_en") else pd.NA
    old = old[old["date"] != dstr]                                  # idempotent: replace this date
    both = pd.concat([new, old], ignore_index=True)
    if both.empty:
        return
    both["sentiment"] = pd.to_numeric(both["sentiment"], errors="coerce")
    cutoff = (pd.to_datetime(both["date"]).max() - pd.Timedelta(days=window_days)).strftime("%Y-%m-%d")
    both = both[both["date"] >= cutoff]                             # rolling window
    both = both.sort_values(["sentiment", "date"], ascending=[False, False], kind="stable")
    both = both.groupby("country", as_index=False, sort=False).head(n).reset_index(drop=True)
    for key, en_col in (("title", "title_en"), ("summary", "summary_en")):
        both[en_col] = both[en_col].fillna("")
        need = both.index[(both[en_col].str.strip() == "") & (both[key].fillna("").str.strip() != "")].tolist()
        if need:
            en = translate_titles(both.loc[need, key].tolist())
            for i, e in zip(need, en):
                both.at[i, en_col] = e
    both[cols].to_csv(npath, index=False)
    print(f"[daily] refreshed negative_titles.csv ({both['country'].nunique()} countries, "
          f"window>={cutoff})", flush=True)

def wmean(g, m):  # n_art-weighted mean of daily => exact per-article mean
    n = g["n_art"].sum()
    return (g[m]*g["n_art"]).sum()/n if n else 0.0

def rederive(daily):
    rel = pd.read_csv(os.path.join(HERE,"tsinghua_relations_long.csv"))[["country","ym","score"]]
    rel = rel.rename(columns={"score":"relations"})
    def agg(freq):
        d = daily.copy(); d["period"] = pd.to_datetime(d["period"])
        key = d["period"].dt.to_period({"W":"W-MON","M":"M"}[freq]).dt.start_time
        d["k"] = key
        rows = []
        for (c,k), g in d.groupby(["country","k"]):
            rec = {"country":c,"period":k.date().isoformat(),"n_art":int(g["n_art"].sum())}
            for m in MEAS: rec[m] = round(wmean(g,m),8)
            rows.append(rec)
        o = pd.DataFrame(rows); o["ym"] = o["period"].str[:7]
        o = o.merge(rel, on=["country","ym"], how="left").drop(columns="ym")
        return o.sort_values(["country","period"])
    return agg("W"), agg("M")

def main():
    d = sys.argv[1] if len(sys.argv)>1 else (datetime.now(timezone.utc).date()-timedelta(days=1)).isoformat()
    print(f"[daily] target {d}", flush=True)
    items = day_rows(date.fromisoformat(d))
    if not items: print("no articles (no edition?)"); return
    with ThreadPoolExecutor(WORKERS) as ex:
        arts = [a for a in ex.map(lambda it: fetch_one(it, d), items) if a]
    with ThreadPoolExecutor(WORKERS) as ex:
        scored = [s for s in ex.map(score, arts) if s]
    print(f"[daily] scored {len(scored)} articles", flush=True)
    new_daily = country_day_rows(scored, d)

    dpath = os.path.join(REPO,"scores_daily.csv")
    daily = pd.read_csv(dpath, encoding="utf-8-sig")
    daily = daily[daily["period"]!=d]                      # idempotent: replace this date
    # keep only canonical cols, align
    cols = ["country","period","n_art"]+MEAS
    daily = pd.concat([daily, new_daily], ignore_index=True)
    # re-attach relations to daily (monthly) for completeness
    rel = pd.read_csv(os.path.join(HERE,"tsinghua_relations_long.csv"))[["country","ym","score"]].rename(columns={"score":"relations"})
    daily["ym"] = daily["period"].str[:7]
    daily = daily.drop(columns=[c for c in ["relations"] if c in daily]).merge(rel,on=["country","ym"],how="left").drop(columns="ym")
    daily = daily.sort_values(["country","period"])
    daily.to_csv(dpath, index=False)
    # daily is bounded to recent years (2016+); rederive only covers that range, so PRESERVE the
    # pre-daily-range weekly/monthly history (full 1949+ from the all-country build) and replace only
    # the recent part. Without this, the daily run would truncate history.
    weekly, monthly = rederive(daily)
    day_min = pd.to_datetime(daily["period"]).min()
    for path, new in (("scores_weekly.csv", weekly), ("scores_monthly.csv", monthly)):
        p = os.path.join(REPO, path)
        if os.path.exists(p):
            old = pd.read_csv(p, encoding="utf-8-sig")
            old = old[pd.to_datetime(old["period"]) < day_min]      # keep history before the daily range
            new = pd.concat([old, new], ignore_index=True)
        new.sort_values(["country","period"]).to_csv(p, index=False)
    print(f"[daily] wrote scores_*.csv (history preserved < {day_min.date()}); coverage to {daily['period'].max()}", flush=True)
    update_recent_titles(scored, d)
    update_negative_titles(scored, d)

if __name__ == "__main__":
    main()
