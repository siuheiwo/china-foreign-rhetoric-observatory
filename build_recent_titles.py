"""Build recent_titles.csv: the 2 most recent People's Daily article titles per country,
for the map hover on the home page. Source = the article-level scored file (titles + URLs +
main_foreign_actors). Only headlines + links are surfaced, never article text."""
import os
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = os.path.join(REPO, "People's Daily 2025-12 to June 12", "scored_articles.csv")
OUT = os.path.join(HERE, "recent_titles.csv")
N = 2  # titles per country

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

    rows = []
    for _, r in df.iterrows():
        actors = [a.strip() for a in str(r["main_foreign_actors"]).split(";")]
        keys = {ACTOR2KEY[a] for a in actors if a in ACTOR2KEY}
        for k in keys:
            rows.append((k, r["date"], str(r["title"]).strip(),
                         r.get("url", ""), r["_row"]))
    long = pd.DataFrame(rows, columns=["country", "date", "title", "url", "_row"])

    # most recent first; later rows on a date treated as later in the day
    long = long.sort_values(["date", "_row"], ascending=[False, False])
    out = (long.groupby("country", as_index=False)
               .head(N)
               .drop(columns="_row")
               .reset_index(drop=True))

    # carry over any English translations already on disk (rebuild must not wipe them);
    # the daily pipeline fills English for headlines that are still missing it.
    prev_en = {}
    if os.path.exists(OUT):
        prev = pd.read_csv(OUT, encoding="utf-8-sig")
        if "title_en" in prev.columns:
            prev_en = dict(zip(prev["title"], prev["title_en"].fillna("")))
    out["title_en"] = out["title"].map(prev_en).fillna("")
    out = out[["country", "date", "title", "title_en", "url"]]
    out.to_csv(OUT, index=False)
    print(f"wrote {OUT}: {len(out)} rows, {out['country'].nunique()} countries, "
          f"{(out['title_en'] == '').sum()} need English")


if __name__ == "__main__":
    main()
