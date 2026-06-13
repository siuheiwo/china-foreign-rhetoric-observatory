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
FLASH, PRO = "deepseek-v4-flash", "deepseek-v4-pro"
WORKERS = 10

GRP = {"US":["United States"], "Russia":["Soviet Union","Russia"], "Japan":["Japan"],
       "UK":["United Kingdom","Britain","England"], "France":["France"], "India":["India"],
       "Germany":["Germany","West Germany","East Germany"],
       "Vietnam":["Vietnam","North Vietnam","South Vietnam"], "South Korea":["South Korea"],
       "Australia":["Australia"], "Indonesia":["Indonesia"], "Pakistan":["Pakistan"]}
LAB2C = {lab: c for c, labs in GRP.items() for lab in labs}
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
    return {"date":art["date"],
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
    weekly, monthly = rederive(daily)
    weekly.to_csv(os.path.join(REPO,"scores_weekly.csv"), index=False)
    monthly.to_csv(os.path.join(REPO,"scores_monthly.csv"), index=False)
    print(f"[daily] wrote scores_*.csv; coverage to {daily['period'].max()}", flush=True)

if __name__ == "__main__":
    main()
