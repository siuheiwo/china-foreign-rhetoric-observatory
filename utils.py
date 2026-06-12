"""Shared helpers for the China Foreign Rhetoric Observatory (offline MVP)."""
import pandas as pd
import streamlit as st

DATA = {"Daily": "scores_daily.csv", "Weekly": "scores_weekly.csv", "Monthly": "scores_monthly.csv"}

# implicit-threat indices + the tone comparison measure
MEASURES = {
    "deepseek":   "DeepSeek implicit threat",
    "lexicon":    "Lexicon (19-word)",
    "lss":        "LSS",
    "negativity": "Negativity (tone)",
}
METHODOLOGY = {
    "deepseek":   "LLM (DeepSeek) score, 0–1, of the implied probability that PRC official media signals "
                  "China will resort to force in the coming days. Few-shot prompt over article summaries.",
    "lexicon":    "Share of tokens matching the validated 19-word implicit-threat lexicon (Wong, PSRM) — "
                  "consequence / 'playing-with-fire' idioms (玩火自焚, 严重后果 …). Sparse by design.",
    "lss":        "Latent Semantic Scaling on jieba-tokenised text; seeded with the 19 implicit-threat "
                  "terms (+1) vs peace terms (−1). Continuous semantic-axis score.",
    "negativity": "General negative tone of the article toward the foreign actor (0 friendly … 1 hostile). "
                  "A salience/tone benchmark, distinct from force-signaling.",
}
ISO3 = {"US":"USA","Russia":"RUS","Japan":"JPN","UK":"GBR","France":"FRA","India":"IND",
        "Germany":"DEU","Vietnam":"VNM","South Korea":"KOR","Australia":"AUS",
        "Indonesia":"IDN","Pakistan":"PAK"}
WINDOW = {"Daily": 365, "Weekly": 52, "Monthly": 24}   # CUSUM/EWMA baseline window per resolution

@st.cache_data
def load_scores(resolution: str) -> pd.DataFrame:
    df = pd.read_csv(DATA[resolution])
    df["period"] = pd.to_datetime(df["period"])
    return df.sort_values(["country", "period"]).reset_index(drop=True)

def cusum_series(values: pd.Series, window: int, drift: float = 0.5) -> list:
    """CUSUM on a rolling-window EWMA-style z-score baseline (spec: yellow>3, red>5)."""
    mean = values.rolling(window, min_periods=max(5, window // 12)).mean()
    std  = values.rolling(window, min_periods=max(5, window // 12)).std()
    c, out = 0.0, []
    for i, v in enumerate(values):
        m, s = mean.iloc[i], std.iloc[i]
        if pd.isna(m) or pd.isna(s):
            out.append(0.0); continue
        z = (v - m) / (s + 1e-6)
        c = max(0.0, c + z - drift)
        out.append(c)
    return out

def alert_for(cusum_last: float) -> tuple:
    if cusum_last > 5: return ("RED", "#b2182b")
    if cusum_last > 3: return ("YELLOW", "#e08214")
    return ("NORMAL", "#4d9221")

def ewma_baseline(values: pd.Series, window: int) -> pd.Series:
    return values.ewm(span=window, min_periods=1).mean()
