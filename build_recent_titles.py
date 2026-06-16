"""Build recent_titles.csv (2 most RECENT) and negative_titles.csv (THE single most NEGATIVE
article in the last 7 days, with a short summary) per country, for the map hover on the home page.
Source = the article-level scored file (titles + URLs + main_foreign_actors + sentiment + summary).
Only headlines + a short summary + links are surfaced, never full article text."""
import os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = os.path.join(REPO, "People's Daily 2025-12 to June 12", "scored_articles.csv")
OUT = os.path.join(HERE, "recent_titles.csv")
OUT_NEG = os.path.join(HERE, "negative_titles.csv")
N = 2  # recent titles per country
NEG_N = 1  # most-negative examples per country (just the one that drives the sentiment)
NEG_WINDOW_DAYS = 7  # "most negative" is scoped to the last N days of available data
SUMMARY_CLIP = 120  # chars of the Chinese summary to keep

# actor name (in main_foreign_actors) -> app country key (matches scores_*.csv), all countries.
# 12 majors keep their friendly keys; every other country uses its full name.
ISO2FRIENDLY = {"USA":"US","GBR":"UK","RUS":"Russia","KOR":"South Korea","JPN":"Japan","FRA":"France",
                "IND":"India","DEU":"Germany","VNM":"Vietnam","AUS":"Australia","IDN":"Indonesia","PAK":"Pakistan"}
def _load_actor2key():
    p = os.path.join(HERE, "actor_to_country.csv")
    m = pd.read_csv(p, encoding="utf-8-sig")
    m = m[m["action"] == "map"]
    return {r["actor"]: ISO2FRIENDLY.get(r["iso3"], r["country"]) for _, r in m.iterrows()}
ACTOR2KEY = _load_actor2key()


def main():
    df = pd.read_csv(SRC, encoding="utf-8-sig")
    df = df[df["title"].notna() & (df["main_foreign_actors"].notna())].copy()
    df["_row"] = range(len(df))  # stable tiebreak: file order within a date

    sent = pd.to_numeric(df.get("sentiment"), errors="coerce")
    summ = df.get("summary", pd.Series([""] * len(df)))
    rows = []
    for (_, r), sv, sm in zip(df.iterrows(), sent, summ):
        actors = [a.strip() for a in str(r["main_foreign_actors"]).split(";")]
        keys = {ACTOR2KEY[a] for a in actors if a in ACTOR2KEY}
        sm = "" if pd.isna(sm) else str(sm).strip().replace("\n", " ")[:SUMMARY_CLIP]
        for k in keys:
            rows.append((k, r["date"], str(r["title"]).strip(),
                         r.get("url", ""), r["_row"], sv, sm))
    long = pd.DataFrame(rows, columns=["country", "date", "title", "url", "_row", "sentiment", "summary"])

    def carry_en(out, key_col, en_col, *paths):
        """Preserve English translations already on disk (rebuild must not wipe them); the daily
        pipeline fills English for any still missing it."""
        prev = {}
        for path in paths:
            if os.path.exists(path):
                p = pd.read_csv(path, encoding="utf-8-sig")
                if key_col in p.columns and en_col in p.columns:
                    prev.update({k: e for k, e in zip(p[key_col], p[en_col].fillna(""))
                                 if isinstance(e, str) and e})
        out[en_col] = out[key_col].map(prev).fillna("")
        return out

    # --- recent: 2 most recent per country (later rows on a date treated as later in the day)
    rec = long.sort_values(["date", "_row"], ascending=[False, False])
    rec = (rec.groupby("country", as_index=False).head(N).reset_index(drop=True))
    rec = carry_en(rec, "title", "title_en", OUT, OUT_NEG)[["country", "date", "title", "title_en", "url"]]
    rec.to_csv(OUT, index=False)
    print(f"wrote {OUT}: {len(rec)} rows, {rec['country'].nunique()} countries, "
          f"{(rec['title_en'] == '').sum()} need English")

    # --- negative: THE single most negative per country within the last NEG_WINDOW_DAYS of data
    cutoff = (pd.to_datetime(long["date"].max()) - pd.Timedelta(days=NEG_WINDOW_DAYS)).strftime("%Y-%m-%d")
    neg = long[(long["date"] >= cutoff) & long["sentiment"].notna()]
    neg = neg.sort_values(["sentiment", "date"], ascending=[False, False])
    neg = (neg.groupby("country", as_index=False).head(NEG_N).reset_index(drop=True))
    neg = carry_en(neg, "title", "title_en", OUT_NEG, OUT)
    neg = carry_en(neg, "summary", "summary_en", OUT_NEG)
    neg = neg[["country", "date", "title", "title_en", "url", "sentiment", "summary", "summary_en"]]
    neg.to_csv(OUT_NEG, index=False)
    print(f"wrote {OUT_NEG}: {len(neg)} rows, {neg['country'].nunique()} countries "
          f"(window >= {cutoff}), {(neg['title_en'] == '').sum()} need title-EN, "
          f"{(neg['summary_en'] == '').sum()} need summary-EN")


if __name__ == "__main__":
    main()
