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


def kperiod_alarm(values: pd.Series, k: int, window: int) -> float:
    if len(values) < 2:
        return 0.0
    base = values.ewm(span=window, min_periods=1).mean().iloc[-1]
    sd = values.rolling(window, min_periods=max(5, window // 12)).std().iloc[-1]
    if pd.isna(sd) or sd == 0:
        sd = values.std()
    return float((values.tail(k).mean() - base) / (sd + 1e-6)) if sd and sd > 0 else 0.0


def status(c):
    return "RED" if c > RED else ("YELLOW" if c > YELLOW else "NORMAL")


def zstatus(z):  # standardized exceedance thresholds
    return "RED" if z >= 3 else ("YELLOW" if z >= 2 else "NORMAL")


rows = []
for res, f in DATA.items():
    df = pd.read_csv(f, parse_dates=["period"]).sort_values(["country", "period"])
    for idx in INDICES:
        for country, g in df.groupby("country"):
            g = g.reset_index(drop=True)
            c = cusum_series(g[idx], WINDOW[res])
            base = g[idx].ewm(span=WINDOW[res], min_periods=1).mean().iloc[-1]
            a3 = kperiod_alarm(g[idx], 3, WINDOW[res])
            a5 = kperiod_alarm(g[idx], 5, WINDOW[res])
            rows.append({
                "resolution": res, "index": idx, "country": country,
                "as_of": g["period"].iloc[-1].date(),
                "latest": round(float(g[idx].iloc[-1]), 4),
                "ewma_baseline": round(float(base), 4),
                "alarm_3p": round(a3, 2), "alarm_3p_alert": zstatus(a3),
                "alarm_5p": round(a5, 2), "alarm_5p_alert": zstatus(a5),
                "cusum": round(float(c[-1]), 2), "cusum_alert": status(c[-1]),
            })

alarms = pd.DataFrame(rows)
alarms.to_csv("alarms.csv", index=False)
print(f"wrote alarms.csv ({len(alarms)} rows = 3 resolutions x 4 indices x 12 countries)\n")

# current alarm board for the headline (DeepSeek) index
for res in DATA:
    sub = alarms[(alarms.resolution == res) & (alarms["index"] == "deepseek")].sort_values("alarm_5p", ascending=False)
    active = sub[(sub.cusum_alert != "NORMAL") | (sub.alarm_5p_alert != "NORMAL") | (sub.alarm_3p_alert != "NORMAL")]
    print(f"[{res}] DeepSeek implicit-threat — countries with any active alert: {len(active)}")
    for _, r in sub.head(5).iterrows():
        print(f"    {r.country:12s} 3p {r.alarm_3p:5.1f}  5p {r.alarm_5p:5.1f}  CUSUM {r.cusum:5.1f}  "
              f"[{r.alarm_3p_alert}/{r.alarm_5p_alert}/{r.cusum_alert}]")
