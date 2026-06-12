# China Foreign Rhetoric Observatory — original specification (verbatim)

> Status: PROPOSED, not built. Captured 2026-06-12 for later. See `FEASIBILITY.md` for assessment.

A public research observatory ("China Foreign Rhetoric Observatory"). Analysis pipeline already exists;
task is to integrate + deploy.

## Tech stack
- Firecrawl API for daily scraping (`FIRECRAWL_API_KEY`)
- DeepSeek API for LLM scoring (`DEEPSEEK_API_KEY`)
- Streamlit dashboard · GitHub Actions automation · Streamlit Cloud deployment

## Daily pipeline (08:00 UTC via GitHub Actions)
1. Firecrawl scrape today's People's Daily (http://paper.people.com.cn)
2. Filter articles mentioning any country in existing country list
3. Append new articles to CSV: `date, country, title, content`
4. Implicit Threat Index scoring (existing lexicon)
5. LSS scoring (existing model)
6. DeepSeek scoring — zero-shot AND few-shot (existing few-shot examples)
7. Update aggregated scores CSV
8. Commit updated CSV to GitHub → Streamlit Cloud auto-refreshes

## Alert system — CUSUM with EWMA baseline
Two-layer: rolling 365d mean/std z-score → CUSUM (drift 0.5). Yellow CUSUM>3, Red CUSUM>5.

## Dashboard — 3 pages
- **P1 Global map**: world choropleth (today's threat index, blue→red); 4 metric cards (global index,
  3-day, 5-day, #countries); top-5 bar chart; per-country CUSUM badges; index toggle
  (Implicit Threat / DeepSeek zero-shot / DeepSeek few-shot / LSS).
- **P2 Historical trends**: annual avg per country 1950–2025; country multi-select; event annotations
  (Cultural Revolution 1966, Tiananmen 1989, Taiwan Strait Crisis 1996, Pelosi 2022).
- **P3 Country drill-down**: country dropdown; 30-day series (3 indexes + EWMA); metric cards; alert
  banner w/ CUSUM; CSV download.

## Deployment
GitHub repo w/ structure; API keys as GitHub + Streamlit Cloud secrets; requirements.txt; step-by-step walkthrough.

## Design
Clean white minimal academic (like digitalembassy.net); English; audience = researchers/policy analysts;
methodology note per page; cite "Implicit Threat Index validated against ICEWS 2016–2025, OOS AUC 0.70 (PSRM 2026)";
subtitle "Tracking China's official diplomatic signaling across bilateral relations · People's Daily corpus 1950–2025".
