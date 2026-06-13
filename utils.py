"""Shared helpers for the China Foreign Rhetoric Observatory (offline MVP)."""
import pandas as pd
import streamlit as st

DATA = {"Daily": "scores_daily.csv", "Weekly": "scores_weekly.csv", "Monthly": "scores_monthly.csv"}

# implicit-threat indices + the tone comparison measure
MEASURES = {
    "deepseek":     "DeepSeek implicit threat",
    "lexicon":      "Lexicon (19-word)",
    "lss":          "LSS",
    "negativity":   "Negativity (tone)",
    "law_deg":      "Frame · legal right",
    "norms_deg":    "Frame · moral / norms",
    "threat_deg":   "Frame · imminent threat",
    "selfdef_deg":  "Frame · self-defense",
    "limited_deg":  "Frame · limited aims",
    "discr_deg":    "Frame · target the few",
}
_FRAME = ("How strongly an article frames China's coercion as justified via this lens (0–1), "
          "from the article-frame LLM coder. ")
METHODOLOGY = {
    "deepseek":   "LLM (DeepSeek) score, 0–1, of the implied probability that PRC official media signals "
                  "China will resort to force in the coming days. Few-shot prompt over article summaries.",
    "lexicon":    "Share of tokens matching the validated 19-word implicit-threat lexicon (Wong, PSRM) — "
                  "consequence / 'playing-with-fire' idioms (玩火自焚, 严重后果 …). Sparse by design.",
    "lss":        "Latent Semantic Scaling on jieba-tokenised text; seeded with the 19 implicit-threat "
                  "terms (+1) vs peace terms (−1). Continuous semantic-axis score.",
    "negativity": "General negative tone of the article toward the foreign actor (0 friendly … 1 hostile). "
                  "A salience/tone benchmark, distinct from force-signaling.",
    "law_deg":     _FRAME + "Coercion framed as a lawful right / the other side as violating international law.",
    "norms_deg":   _FRAME + "Coercion framed as morally right / on the side of justice and historical trend.",
    "threat_deg":  _FRAME + "The other side framed as an imminent, serious threat (迫近威胁) to China.",
    "selfdef_deg": _FRAME + "Coercion framed as forced self-defense / counter-action (被迫还击).",
    "limited_deg": _FRAME + "Coercion framed as limited, proportionate, a last resort — not conquest.",
    "discr_deg":   _FRAME + "Coercion framed as targeting only a guilty few, not ordinary people.",
}
ISO3 = {"US":"USA","Russia":"RUS","Japan":"JPN","UK":"GBR","France":"FRA","India":"IND",
        "Germany":"DEU","Vietnam":"VNM","South Korea":"KOR","Australia":"AUS",
        "Indonesia":"IDN","Pakistan":"PAK"}
WINDOW = {"Daily": 365, "Weekly": 52, "Monthly": 24}   # CUSUM/EWMA baseline window per resolution

import os

@st.cache_data
def _read(path: str, _mtime: float) -> pd.DataFrame:
    df = pd.read_csv(path, encoding="utf-8-sig")     # utf-8-sig strips the BOM in the header
    df["period"] = pd.to_datetime(df["period"])
    return df.sort_values(["country", "period"]).reset_index(drop=True)

def load_scores(resolution: str) -> pd.DataFrame:
    # mtime in the cache key => refresh picks up rebuilt CSVs automatically
    p = DATA[resolution]
    return _read(p, os.path.getmtime(p))

def last_updated(resolution: str = "Daily") -> str:
    df = load_scores(resolution)
    return str(df["period"].max().date())

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

def standardize(s: pd.Series) -> pd.Series:
    """Within-series z-score so indices on different scales become comparable."""
    sd = s.std()
    return (s - s.mean()) / sd if sd and sd > 0 else s * 0.0

def kperiod_alarm(values: pd.Series, k: int, window: int) -> float:
    """How many SD the last-k-period average sits above the EWMA baseline.
    Standardized => comparable across countries/indices. (3- and 5-period alarms.)"""
    if len(values) < 2:
        return 0.0
    base = values.ewm(span=window, min_periods=1).mean().iloc[-1]
    sd = values.rolling(window, min_periods=max(5, window // 12)).std().iloc[-1]
    if pd.isna(sd) or sd == 0:
        sd = values.std()
    recent = values.tail(k).mean()
    return float((recent - base) / (sd + 1e-6)) if sd and sd > 0 else 0.0

def z_alert(z: float) -> tuple:
    """Alert from a standardized exceedance (SD units): >=3 red, >=2 yellow."""
    if z >= 3: return ("RED", "#b2182b")
    if z >= 2: return ("YELLOW", "#e08214")
    return ("NORMAL", "#4d9221")
