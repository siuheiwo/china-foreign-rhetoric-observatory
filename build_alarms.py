"""Materialise the alarm board: CUSUM change-detection alert per country, for every
index and resolution. Alarm = CUSUM (departure from each country's own baseline),
NOT the raw level. Yellow > 3, Red > 5. Writes alarms.csv and prints current alerts."""
import pandas as pd

DATA = {"Daily": "scores_daily.csv", "Weekly": "scores_weekly.csv", "Monthly": "scores_monthly.csv"}
WINDOW = {"Daily": 365, "Weekly": 52, "Monthly": 24}
INDICES = ["deepseek", "lexicon", "lss", "negativity"]
DRIFT, YELLOW, RED = 0.5, 3.0, 5.0


def cusum_series(values: pd.Series, window: int, drift: float = DRIFT):
    mean = values.rolling(window, min_periods=max(5, window // 12)).mean()
    std = values.rolling(window, min_periods=max(5, window // 12)).std()
    c, out = 0.0, []
    for i, v in enumerate(values):
        m, s = mean.iloc[i], std.iloc[i]
        if pd.isna(m) or pd.isna(s):
            out.append(0.0); continue
        z = (v - m) / (s + 1e-6)
        c = max(0.0, c + z - drift)
        out.append(c)
    return out


def status(c):
    return "RED" if c > RED else ("YELLOW" if c > YELLOW else "NORMAL")


rows = []
for res, f in DATA.items():
    df = pd.read_csv(f, parse_dates=["period"]).sort_values(["country", "period"])
    for idx in INDICES:
        for country, g in df.groupby("country"):
            g = g.reset_index(drop=True)
            c = cusum_series(g[idx], WINDOW[res])
            base = g[idx].ewm(span=WINDOW[res], min_periods=1).mean().iloc[-1]
            rows.append({
                "resolution": res, "index": idx, "country": country,
                "as_of": g["period"].iloc[-1].date(),
                "latest": round(float(g[idx].iloc[-1]), 4),
                "ewma_baseline": round(float(base), 4),
                "cusum": round(float(c[-1]), 2),
                "alert": status(c[-1]),
            })

alarms = pd.DataFrame(rows)
alarms.to_csv("alarms.csv", index=False)
print(f"wrote alarms.csv ({len(alarms)} rows = 3 resolutions x 4 indices x 12 countries)\n")

# current alarm board for the headline (DeepSeek) index
for res in DATA:
    sub = alarms[(alarms.resolution == res) & (alarms["index"] == "deepseek")].sort_values("cusum", ascending=False)
    active = sub[sub.alert != "NORMAL"]
    print(f"[{res}] DeepSeek implicit-threat — active alerts: "
          f"{len(active)} (red {sum(sub.alert=='RED')}, yellow {sum(sub.alert=='YELLOW')})")
    for _, r in sub.head(5).iterrows():
        print(f"    {r.country:12s} CUSUM {r.cusum:5.1f}  {r.alert:7s} (latest {r.latest})")
