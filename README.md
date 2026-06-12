# China Foreign Rhetoric Observatory — offline MVP (try, June 2026)

Streamlit dashboard over the implicit-threat measures for the 12 Tsinghua great powers, at
**daily / weekly / monthly** resolution. This is the offline core (reads CSVs, no APIs); the daily
Firecrawl/DeepSeek pipeline + deployment are the next steps (see `FEASIBILITY.md`).

## Run locally
```bash
cd "observatory try June 2026"
pip install -r requirements.txt
Rscript build_observatory_data.R      # (re)build scores_{daily,weekly,monthly}.csv
streamlit run app.py
```

## Files
- `build_observatory_data.R` — merges the 4 measures + Tsinghua relations → `scores_{daily,weekly,monthly}.csv`
  (12 powers; empty period = 0 for the threat indices; relations attached monthly).
- `app.py` — Page 1 global choropleth, metric cards, top-5, CUSUM alert badges.
- `pages/2_Historical_Trends.py` — annual averages 1950–2025, event annotations.
- `pages/3_Country_Drilldown.py` — recent series (3 indices + EWMA), alert banner, CSV download.
- `utils.py` — data loader, measure metadata, ISO3 map, CUSUM/EWMA.

## Indices
DeepSeek implicit threat · Lexicon (PSRM 19-word) · LSS · Negativity (tone benchmark).

## Still to do for full deployment
1. Daily pipeline `daily_update.py` (Firecrawl scrape → classify → score → append CSV → commit).
2. GitHub repo + Actions cron (08:00 UTC) + secrets (`DEEPSEEK_API_KEY`, `FIRECRAWL_API_KEY`).
3. Streamlit Cloud connect + secrets → public URL.
