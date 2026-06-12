# Feasibility assessment — China Foreign Rhetoric Observatory

**Verdict: feasible, and a strong idea — but not as a one-shot "integrate and deploy."** ~80% is
standard work; the other 20% hides four real blockers that must be decided BEFORE building, plus a
factual-accuracy fix. Nothing here is a dealbreaker; each has a clean path. Rough effort: a working
MVP in ~2–4 focused days, production-hardened in ~1–2 weeks.

## What's straightforward (low risk)
- **Streamlit 3-page dashboard** — choropleth, metric cards, bar charts, multi-select, drill-down,
  CSV download, event annotations. All standard Plotly/Streamlit.
- **CUSUM/EWMA alerts** — pure pandas, trivial. (One inconsistency to fix: the pasted `cusum_alert`
  uses `threshold=4`, but the text says Yellow>3 / Red>5 — I'll wire two thresholds 3 & 5.)
- **DeepSeek zero-shot + few-shot scoring** — scripts already exist and are validated
  (`run_threat_zeroshot_*` / `run_threat_examples_*`). Daily volume is tiny → cents/day.
- **GitHub Actions cron at 08:00 UTC** + **secrets** (GitHub + Streamlit Cloud) — routine.

## The four real blockers (decide first)

### 1. Data size vs GitHub / Streamlit Cloud  ← biggest
The corpus files are **300 MB–11 GB** (`article_classify_full.csv` 303 MB, `foreign_affairs_iv.csv`
308 MB, `comprehensive_dataset.csv` 11 GB). GitHub rejects >100 MB files; Streamlit Cloud free tier
has ~1 GB RAM. **You cannot commit or load these.** Fix: split the data layer —
- keep the heavy historical corpus OUT of git (local / external / Git LFS),
- the repo + dashboard read only a **small pre-aggregated `country_day_scores.csv`** (country × date ×
  4 indices) and a **`country_year_scores.csv`** for the 1950–2025 page. These are KB–few MB. The
  daily job appends one day's rows to the live file and commits just that. This is the right design
  anyway; just needs building deliberately.

### 2. Daily country tagging must match the existing convention
Existing country assignment is **LLM-extracted `main_foreign_actors`** (normalized names), not raw
string matching. The spec's "filter articles mentioning any country" (substring) would produce a
DIFFERENT, noisier country list than the historical data → the live series wouldn't be comparable to
history. Fix: run new articles through the SAME classify step (a DeepSeek call) to get
`main_foreign_actors`, then map to the country list. Slightly more cost; preserves comparability.

### 3. The "Implicit Threat Index (lexicon)" and "LSS (model)" need their artifacts
- Lexicon path: `threat_perception_lexicon.csv` is hand-supplied (frame dicts are word2vec-generated,
  in `~/Desktop/people's daily 2025`). Confirm which lexicon defines the public "Implicit Threat Index."
- **LSS**: scoring NEW text needs the **trained LSS model object** (quanteda textmodel_lss), not just
  the score columns. If only `threat_peace_lss.csv` (scores) exists and the model wasn't saved, LSS
  must be retrained/saved once before daily scoring can run. Need to confirm the saved model exists.

### 4. People's Daily scraping robustness
`paper.people.com.cn` uses date-keyed layout URLs (版面 → article). Firecrawl can do it, but the
selectors/URL pattern will need building and will break when the site changes. Also note your historical
corpus came via a different source (马克数据网 snapshots) — the live `content` formatting will differ
slightly; the cleaning regex must be applied identically.

## Factual-accuracy fix (important for a PUBLIC site)
The proposed citation — *"Implicit Threat Index validated against ICEWS 2016–2025, OOS AUC 0.70 (PSRM
2026)"* — **does not match your own validated findings**. Per the project record: the OOS forecasting
result that held (6/6 splits) was the **DeepSeek frame** measure; the median-line / implicit-threat OOS
was **null on AUC**, and you explicitly concluded AUC is the wrong yardstick (report the incremental-LR
test instead). Publishing "OOS AUC 0.70" for the Implicit Threat Index would overstate and contradict
the manuscript. Reword to exactly what's defensible before going public (I can draft it).

## Other notes
- **Country → ISO mapping** for the choropleth: historical entities (Soviet Union, East/West Germany)
  don't map to today's map — need a mapping table + a decision on how to render pre-1991 USSR.
- **DeepSeek key**: the key used this session was shared in plaintext — rotate it and store only as a
  secret before any public deployment.
- **Cost/quotas**: Firecrawl + DeepSeek daily are cheap, but set quota guards in the Action.
- **Cadence reality**: dashboard is only as "daily" as the scrape; add a "last updated" stamp and a
  fail-soft if a day's scrape returns nothing.

## Questions I'll need answered before building (do NOT need now)
1. File paths: the per-country scored CSVs (live + historical), the **lexicon**, the **saved LSS model**,
   and the **few-shot examples** file.
2. Which measure is the public "Implicit Threat Index" — the lexicon `threat_pct`, or the chosen
   MS-summary LLM measure? (4 toggles implied: lexicon / DeepSeek-ZS / DeepSeek-FS / LSS.)
3. Confirm the canonical country list + labels to expose publicly.
4. Public or private repo? Any embargo on unpublished results before the book/PSRM piece is out?
5. The exact, defensible validation sentence to cite.

## Suggested build order (when you greenlight)
1. Build the aggregation layer (`country_day_scores.csv`, `country_year_scores.csv`) from existing data.
2. Streamlit app reading those (works offline, no APIs) — get the 3 pages right.
3. Add CUSUM/EWMA on the aggregates.
4. Daily pipeline (scrape → classify → score → aggregate → commit) as a separate, well-tested module.
5. GitHub Actions + secrets + Streamlit Cloud, then the deployment walkthrough.
