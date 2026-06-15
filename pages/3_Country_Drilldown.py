"""Page 3: Country drill-down — STANDARDIZED recent series (comparable indices),
3-/5-period + CUSUM alarms, EWMA baseline, CSV download."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from utils import (load_scores, MEASURES, WINDOW, cusum_series, alert_for,
                   kperiod_alarm, z_alert, standardize, ewma_baseline)

st.set_page_config(page_title="Country drill-down · Observatory", layout="wide")
st.title("Country drill-down")

with st.sidebar:
    resolution = st.radio("Aggregation", list(WINDOW.keys()), index=2)
    n_periods = st.slider("Periods shown", 10, 120, 30)

df = load_scores(resolution)
country = st.selectbox("Country", sorted(df["country"].unique()))
g = df[df["country"] == country].sort_values("period").reset_index(drop=True)
w = WINDOW[resolution]

# standardized (z) versions so the three indices are comparable on one axis
for m in ["deepseek", "lexicon", "lss"]:
    g[m + "_z"] = standardize(g[m])
g["ewma_z"] = ewma_baseline(g["deepseek_z"], w)
g["cusum"] = cusum_series(g["deepseek"], w)
a3 = kperiod_alarm(g["deepseek"], 3, w)
a5 = kperiod_alarm(g["deepseek"], 5, w)
cu = g["cusum"].iloc[-1]

# headline alert = worst of the three signals
cands = [("3-period", *z_alert(a3)), ("5-period", *z_alert(a5)), ("CUSUM", *alert_for(cu))]
rank = {"NORMAL": 0, "YELLOW": 1, "RED": 2}
worst = max(cands, key=lambda c: rank[c[1]])
st.markdown(f"<div style='background:{worst[2]};color:white;padding:10px 16px;border-radius:8px'>"
            f"<b>{worst[1]} alert</b> — {country} · driven by {worst[0]} "
            f"(3p {a3:.1f}σ · 5p {a5:.1f}σ · CUSUM {cu:.1f})</div>", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Latest (DeepSeek)", f"{g['deepseek'].iloc[-1]:.3f}")
c2.metric("Alarm 3-period (σ)", f"{a3:.2f}")
c3.metric("Alarm 5-period (σ)", f"{a5:.2f}")
c4.metric("CUSUM", f"{cu:.1f}")

recent = g.tail(n_periods)
fig = go.Figure()
for m, col in [("deepseek_z", "#b2182b"), ("lexicon_z", "#762a83"), ("lss_z", "#1b7837")]:
    fig.add_trace(go.Scatter(x=recent["period"], y=recent[m],
                             name=MEASURES[m.replace("_z", "")], line=dict(color=col)))
fig.add_trace(go.Scatter(x=recent["period"], y=recent["ewma_z"], name="EWMA baseline (DeepSeek)",
                         line=dict(color="grey", dash="dot")))
# Tsinghua relations on a secondary axis, REVERSED (sign-flipped) so that worse relations read
# HIGH — i.e. it now moves WITH the threat indices, which is easier to read at a glance.
if "relations" in recent and recent["relations"].notna().any():
    fig.add_trace(go.Scatter(x=recent["period"], y=-recent["relations"],
                             name="Tsinghua tension (reversed, right)",
                             line=dict(color="#2166ac", dash="dash"), yaxis="y2"))
    fig.update_layout(yaxis2=dict(title="Tsinghua tension (reversed: high = worse relations)",
                                  overlaying="y", side="right", showgrid=False))
fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), legend_title="",
                  yaxis_title="standardized (z-score, SD units)")
st.plotly_chart(fig, use_container_width=True)

st.download_button("Download this country's series (CSV)",
                   g.to_csv(index=False).encode("utf-8"),
                   file_name=f"{country}_{resolution.lower()}.csv", mime="text/csv")

st.divider()
st.caption("**Methodology.** Lines are z-scored per index (mean 0, SD 1) so DeepSeek / Lexicon / LSS "
           "are comparable. Alarms are standardized: 3-/5-period = SD of the recent average above the "
           "EWMA baseline (yellow≥2, red≥3); CUSUM = sustained drift (yellow>3, red>5). "
           "Empty period (0 articles) scored 0.")
