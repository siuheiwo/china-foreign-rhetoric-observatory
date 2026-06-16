"""One-off: fill English (title_en / summary_en) for recent_titles.csv + negative_titles.csv via
DeepSeek, batched. Idempotent — only translates rows still missing English. Going forward the daily
pipeline fills new ones."""
import os, json, urllib.request, time
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
KEY = os.environ["DEEPSEEK_API_KEY"]
EP = "https://api.deepseek.com/v1/chat/completions"
SYS = ("You translate Chinese newspaper headlines/summaries into concise natural English. Input is a "
       "JSON array of Chinese strings. Output JSON {\"t\":[\"en1\",...]} with exactly one English string "
       "per input, same order. Keep any parenthetical column name translated. Output JSON only.")

def translate(strings, batch=40):
    out = []
    for i in range(0, len(strings), batch):
        chunk = strings[i:i+batch]
        body = {"model":"deepseek-v4-pro","temperature":0,"response_format":{"type":"json_object"},
                "messages":[{"role":"system","content":SYS},
                            {"role":"user","content":json.dumps(chunk, ensure_ascii=False)}]}
        en = [""]*len(chunk)
        for attempt in range(4):
            try:
                req = urllib.request.Request(EP, data=json.dumps(body).encode(),
                    headers={"Authorization":f"Bearer {KEY}","Content-Type":"application/json"}, method="POST")
                with urllib.request.urlopen(req, timeout=180) as r:
                    ct = json.loads(json.loads(r.read())["choices"][0]["message"]["content"])
                t = ct.get("t")
                if isinstance(t, list) and len(t) == len(chunk):
                    en = [str(x) for x in t]; break
            except Exception:
                time.sleep(2*(attempt+1))
        out.extend(en)
        print(f"  translated {min(i+batch,len(strings))}/{len(strings)}", flush=True)
    return dict(zip(strings, out))

def fill(path, cols):
    df = pd.read_csv(path, encoding="utf-8-sig")
    for src, en in cols:
        if src not in df.columns: continue
        if en not in df.columns: df[en] = ""
        df[en] = df[en].fillna("")
        need = sorted({str(s) for s, e in zip(df[src], df[en]) if str(s).strip() and not str(e).strip()})
        if not need: continue
        print(f"{os.path.basename(path)}: translating {len(need)} unique {en} ...")
        m = translate(need)
        df[en] = [m.get(str(s), e) if (str(s).strip() and not str(e).strip()) else e
                  for s, e in zip(df[src], df[en])]
    df.to_csv(path, index=False)
    print(f"wrote {path}")

fill(os.path.join(HERE, "recent_titles.csv"), [("title","title_en")])
fill(os.path.join(HERE, "negative_titles.csv"), [("title","title_en"), ("summary","summary_en")])
