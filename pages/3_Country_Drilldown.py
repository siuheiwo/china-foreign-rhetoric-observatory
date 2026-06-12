"""Page 3: Country drill-down — recent series, all indices + EWMA baseline, alert, download."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from utils import load_scores, MEASURES, METHODOLOGY, WINDOW, cusum_series, alert_for, ewma_baseline

st.set_page_config(page_title="Country drill-down · Observatory", layout="wide")
st.title("Country drill-down")

with st.sidebar:
    resolution = st.radio("Aggregation", list(WINDOW.keys()), index=2)
    n_periods = st.slider("Periods shown", 10, 120, 30)

df = load_scores(resolution)
country = st.selectbox("Country", sorted(df["country"].unique()))
g = df[df["country"] == country].sort_values("period").reset_index(drop=True)

# headline index = DeepSeek; EWMA baseline on it
g["ewma"] = ewma_baseline(g["deepseek"], WINDOW[resolution])
g["cusum"] = cusum_series(g["deepseek"], WINDOW[resolution])
recent = g.tail(n_periods)

status, color = alert_for(g["cusum"].iloc[-1])
st.markdown(f"<div style='background:{color};color:white;padding:10px 16px;border-radius:8px'>"
            f"<b>{status} alert</b> — {country} · CUSUM {g['cusum'].iloc[-1]:.1f} "
            f"(yellow&gt;3, red&gt;5)</div>", unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Latest (DeepSeek)", f"{g['deepseek'].iloc[-1]:.3f}")
c2.metric("3-period avg", f"{g['deepseek'].tail(3).mean():.3f}")
c3.metric("5-period avg", f"{g['deepseek'].tail(5).mean():.3f}")
c4.metric("EWMA baseline", f"{g['ewma'].iloc[-1]:.3f}")

fig = go.Figure()
for m, col in [("deepseek", "#b2182b"), ("lexicon", "#762a83"), ("lss", "#1b7837")]:
    fig.add_trace(go.Scatter(x=recent["period"], y=recent[m], name=MEASURES[m], line=dict(color=col)))
fig.add_trace(go.Scatter(x=recent["period"], y=recent["ewma"], name="EWMA baseline (DeepSeek)",
                         line=dict(color="grey", dash="dot")))
fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), legend_title="")
st.plotly_chart(fig, use_container_width=True)

st.download_button("Download this country's series (CSV)",
                   g.to_csv(index=False).encode("utf-8"),
                   file_name=f"{country}_{resolution.lower()}.csv", mime="text/csv")

st.divider()
st.caption("**Methodology.** Indices: " +
           " · ".join(f"{MEASURES[k]}" for k in ["deepseek", "lexicon", "lss"]) +
           f". Alert from CUSUM on the DeepSeek index (baseline window {WINDOW[resolution]} "
           f"{resolution.lower()} periods). Empty period (0 articles) scored 0.")
