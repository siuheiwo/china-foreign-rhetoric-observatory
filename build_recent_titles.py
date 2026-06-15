"""Build recent_titles.csv (2 most RECENT) and negative_titles.csv (2 most NEGATIVE in the
last 3 days) per country, for the map hover on the home page. Source = the article-level scored
file (titles + URLs + main_foreign_actors + sentiment). Only headlines + links are surfaced,
never article text."""
import os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = os.path.join(REPO, "People's Daily 2025-12 to June 12", "scored_articles.csv")
OUT = os.path.join(HERE, "recent_titles.csv")
OUT_NEG = os.path.join(HERE, "negative_titles.csv")
N = 2  # titles per country
NEG_WINDOW_DAYS = 3  # "most negative" is scoped to the last N days of available data

# actor name (in main_foreign_actors) -> app country key (matches scores_*.csv / ISO3)
ACTOR2KEY = {
    "United States": "US", "USA": "US", "America": "US",
    "United Kingdom": "UK", "Britain": "UK",
    "Russia": "Russia", "Russian Federation": "Russia",
    "South Korea": "South Korea", "Republic of Korea": "South Korea", "Korea": "South Korea",
    "Japan": "Japan", "France": "France", "India": "India", "Germany": "Germany",
    "Vietnam": "Vietnam", "Australia": "Australia", "Indonesia": "Indonesia", "Pakistan": "Pakistan",
}


def main():
    df = pd.read_csv(SRC, encoding="utf-8-sig")
    df = df[df["title"].notna() & (df["main_foreign_actors"].notna())].copy()
    df["_row"] = range(len(df))  # stable tiebreak: file order within a date

    sent = pd.to_numeric(df.get("sentiment"), errors="coerce")
    rows = []
    for (_, r), sv in zip(df.iterrows(), sent):
        actors = [a.strip() for a in str(r["main_foreign_actors"]).split(";")]
        keys = {ACTOR2KEY[a] for a in actors if a in ACTOR2KEY}
        for k in keys:
            rows.append((k, r["date"], str(r["title"]).strip(),
                         r.get("url", ""), r["_row"], sv))
    long = pd.DataFrame(rows, columns=["country", "date", "title", "url", "_row", "sentiment"])

    def carry_english(out, *paths):
        """Preserve any English translations already on disk (rebuild must not wipe them),
        pulling from every given file (so recent + negative share translations); the daily
        pipeline fills English for headlines still missing it."""
        prev_en = {}
        for path in paths:
            if os.path.exists(path):
                prev = pd.read_csv(path, encoding="utf-8-sig")
                if "title_en" in prev.columns:
                    prev_en.update({t: e for t, e in zip(prev["title"], prev["title_en"].fillna(""))
                                    if isinstance(e, str) and e})
        out["title_en"] = out["title"].map(prev_en).fillna("")
        return out

    # --- recent: 2 most recent per country (later rows on a date treated as later in the day)
    rec = long.sort_values(["date", "_row"], ascending=[False, False])
    rec = (rec.groupby("country", as_index=False).head(N).reset_index(drop=True))
    rec = carry_english(rec, OUT, OUT_NEG)[["country", "date", "title", "title_en", "url"]]
    rec.to_csv(OUT, index=False)
    print(f"wrote {OUT}: {len(rec)} rows, {rec['country'].nunique()} countries, "
          f"{(rec['title_en'] == '').sum()} need English")

    # --- negative: 2 most negative per country within the last NEG_WINDOW_DAYS of data
    cutoff = (pd.to_datetime(long["date"].max()) - pd.Timedelta(days=NEG_WINDOW_DAYS)).strftime("%Y-%m-%d")
    neg = long[(long["date"] >= cutoff) & long["sentiment"].notna()]
    neg = neg.sort_values(["sentiment", "date"], ascending=[False, False])
    neg = (neg.groupby("country", as_index=False).head(N).reset_index(drop=True))
    neg = carry_english(neg, OUT_NEG, OUT)
    neg = neg[["country", "date", "title", "title_en", "url", "sentiment"]]
    neg.to_csv(OUT_NEG, index=False)
    print(f"wrote {OUT_NEG}: {len(neg)} rows, {neg['country'].nunique()} countries "
          f"(window >= {cutoff}), {(neg['title_en'] == '').sum()} need English")


if __name__ == "__main__":
    main()
