"""Scrape People's Daily web edition (new layout) over a date range — DIRECT HTTP, no Firecrawl
(pages are plain server-rendered HTML). Captures: date, page(node), section(版面), title, author, url, text.
Resumable (skips URLs already in pd_articles.csv).

Usage:
  python3 scrape_pd.py 2026-06-13              # one day
  python3 scrape_pd.py 2025-12-01 2026-06-12   # range
"""
import sys, re, csv, html, time, urllib.request, gzip
from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor
import os

OUT = os.path.join(os.path.dirname(__file__), "pd_articles.csv")
NODE = "https://paper.people.com.cn/rmrb/pc/layout/{ym}/{d}/node_{n:02d}.html"
UA = {"User-Agent": "Mozilla/5.0 (research; contact siuwong@aus.edu)"}
WORKERS = 10


def get(url, tries=4):
    for t in range(tries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=40) as r:
                raw = r.read()
            if r.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            return raw.decode("utf-8", "replace")
        except Exception:
            time.sleep(1.5 * (t + 1))
    return ""


def node_urls(h, ym, d):
    ns = sorted({int(m) for m in re.findall(r"/node_(\d+)\.html", h)})
    return [NODE.format(ym=ym, d=d, n=n) for n in ns] or None


def section_name(h):
    m = re.search(r"第\s*\d+\s*版[：:][^<\"\n]+", h)
    return m.group(0).strip() if m else ""


def node_articles(h, base):
    out = []
    for m in re.finditer(r'href="([^"]*content_(\d+)\.html)"[^>]*>\s*([^<]+)', h):
        url = urllib.parse.urljoin(base, m.group(1)).replace("http://", "https://")
        out.append((url, html.unescape(m.group(3)).strip()))
    # dedupe by url, keep first title
    seen = {}
    for url, title in out:
        seen.setdefault(url, title)
    return [(u, t) for u, t in seen.items()]


def parse_article(h):
    t = re.search(r"<h1[^>]*>(.*?)</h1>", h, re.S) or re.search(r"<title>(.*?)</title>", h, re.S)
    title = html.unescape(re.sub(r"<[^>]+>", "", t.group(1))).strip() if t else ""
    a = re.search(r"(本报记者|新华社记者|本报评论员)\s*([一-龥]{2,4}(?:[ 　]+[一-龥]{2,4})*)?", h)
    author = (a.group(1) + (" " + a.group(2) if a.group(2) else "")).strip() if a else ""
    m = re.search(r'<div class="article"[^>]*>(.*?)</div>\s*</div>', h, re.S) or \
        re.search(r'<div class="article"[^>]*>(.*?)</div>', h, re.S)
    body = m.group(1) if m else ""
    paras = [html.unescape(re.sub(r"<[^>]+>", "", p)).strip() for p in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S)]
    drop = re.compile(r"^(人民日报|《人民日报》|\(?\d{4}年|本报记者|新华社|-->|$)")
    text = " ".join(re.sub(r"\s+", " ", p) for p in paras if p and not drop.match(p))
    return title, author, text


import urllib.parse


def day_rows(dt: date):
    ym, d = dt.strftime("%Y%m"), dt.strftime("%d")
    items = []  # (url, page, section, list_title)
    for page in range(1, 41):                      # enumerate pages until a gap (404 -> empty)
        nd = NODE.format(ym=ym, d=d, n=page)
        hh = get(nd)
        arts = node_articles(hh, nd) if hh else []
        if not arts:
            if page == 1:
                continue                            # some days start at a different page; allow one more
            break                                   # contiguous run ended
        sec = section_name(hh)
        for url, title in arts:
            items.append((url, page, sec, title))
    # dedupe by url
    seen = {}
    for url, page, sec, title in items:
        seen.setdefault(url, (page, sec, title))
    return [(u, *v) for u, v in seen.items()]


def fetch_one(item, dstr):
    url, page, sec, list_title = item
    h = get(url)
    title, author, text = parse_article(h)
    return {"date": dstr, "page": page, "section": sec,
            "title": title or list_title, "author": author, "url": url, "content": text}


def daterange(a, b):
    cur = a
    while cur <= b:
        yield cur; cur += timedelta(days=1)


def main():
    args = sys.argv[1:]
    start = date.fromisoformat(args[0])
    end = date.fromisoformat(args[1]) if len(args) > 1 else start
    done = set()
    if os.path.exists(OUT):
        with open(OUT, encoding="utf-8") as f:
            done = {r["url"] for r in csv.DictReader(f)}
    new = not os.path.exists(OUT)
    fh = open(OUT, "a", newline="", encoding="utf-8")
    w = csv.DictWriter(fh, fieldnames=["date", "page", "section", "title", "author", "url", "content"])
    if new:
        w.writeheader()
    for dt in daterange(start, end):
        dstr = dt.isoformat()
        items = [it for it in day_rows(dt) if it[0] not in done]
        if not items:
            print(f"{dstr}: 0 new", flush=True); continue
        t0 = time.time()
        with ThreadPoolExecutor(WORKERS) as ex:
            for rec in ex.map(lambda it: fetch_one(it, dstr), items):
                w.writerow(rec); done.add(rec["url"])
        fh.flush()
        print(f"{dstr}: +{len(items)} articles in {time.time()-t0:.0f}s", flush=True)
    fh.close()


if __name__ == "__main__":
    main()
