"""China Foreign Rhetoric Observatory — Page 1: Global map. Offline MVP."""
import pandas as pd
import plotly.express as px
import streamlit as st
from utils import (load_scores, MEASURES, METHODOLOGY, ISO3, WINDOW,
                   cusum_series, alert_for, kperiod_alarm, z_alert)

st.set_page_config(page_title="China Foreign Rhetoric Observatory", layout="wide")

st.title("China Foreign Rhetoric Observatory")
st.caption("Tracking China's official diplomatic signaling across bilateral relations · "
           "People's Daily corpus 1950–2025")

with st.sidebar:
    st.header("Controls")
    resolution = st.radio("Aggregation", list(WINDOW.keys()), index=2)
    measure = st.selectbox("Index", list(MEASURES.keys()),
                           format_func=lambda k: MEASURES[k], index=0)

df = load_scores(resolution)
latest = df["period"].max()
cur = df[df["period"] == latest].copy()
cur["iso3"] = cur["country"].map(ISO3)

# --- metric cards ---
def global_avg(periods_back):
    ps = sorted(df["period"].unique())[-periods_back:]
    return df[df["period"].isin(ps)][measure].mean()

c1, c2, c3, c4 = st.columns(4)
c1.metric(f"Global index ({latest.date()})", f"{cur[measure].mean():.3f}")
c2.metric("3-period avg", f"{global_avg(3):.3f}")
c3.metric("5-period avg", f"{global_avg(5):.3f}")
c4.metric("Countries monitored", f"{cur['country'].nunique()}")

# --- choropleth ---
st.subheader(f"{MEASURES[measure]} — latest period ({latest.date()})")
fig = px.choropleth(cur, locations="iso3", color=measure, hover_name="country",
                    color_continuous_scale="RdBu_r", range_color=(cur[measure].min(), cur[measure].max()))
fig.update_layout(margin=dict(l=0, r=0, t=0, b=0), geo=dict(showframe=False, projection_type="natural earth"))
st.plotly_chart(fig, use_container_width=True)

left, right = st.columns(2)
# --- top 5 ---
with left:
    st.subheader("Top 5 by latest score")
    top = cur.sort_values(measure, ascending=False).head(5)
    bar = px.bar(top, x=measure, y="country", orientation="h", color=measure,
                 color_continuous_scale="RdBu_r")
    bar.update_layout(margin=dict(l=0, r=0, t=0, b=0), yaxis=dict(autorange="reversed"),
                      coloraxis_showscale=False)
    st.plotly_chart(bar, use_container_width=True)

# --- alarm board: 3-period + 5-period (standardized exceedance) + CUSUM ---
with right:
    st.subheader("Alarm status")
    st.caption("3-/5-period = SD above each country's EWMA baseline (yellow≥2, red≥3); "
               "CUSUM = sustained drift (yellow>3, red>5). Standardized → comparable across countries.")
    rows = []
    for ctry, g in df.groupby("country"):
        s = g[measure].reset_index(drop=True)
        a3, a5 = kperiod_alarm(s, 3, WINDOW[resolution]), kperiod_alarm(s, 5, WINDOW[resolution])
        cu = cusum_series(s, WINDOW[resolution])[-1] if len(s) else 0.0
        rows.append((ctry, a3, a5, cu))
    rows.sort(key=lambda r: -max(r[2], r[3] / 5))   # rank by 5-period alarm (CUSUM scaled in)

    def badge(label, color):
        return (f"<span style='background:{color};color:white;padding:1px 7px;border-radius:9px;"
                f"font-size:0.72em'>{label}</span>")
    for ctry, a3, a5, cu in rows:
        s3, c3 = z_alert(a3); s5, c5 = z_alert(a5); sc, cc = alert_for(cu)
        st.markdown(
            f"<span style='display:inline-block;width:96px'>{ctry}</span>"
            f"{badge(f'3p {a3:.1f}', c3)} {badge(f'5p {a5:.1f}', c5)} {badge(f'CUSUM {cu:.1f}', cc)}",
            unsafe_allow_html=True)

st.divider()
st.caption(f"**Methodology — {MEASURES[measure]}.** {METHODOLOGY[measure]}  "
           "Empty period (0 articles) is scored 0. Alerts: CUSUM>3 yellow, >5 red, "
           f"baseline window = {WINDOW[resolution]} {resolution.lower()} periods.")
st.caption("Implicit Threat Index from Wong, *Forecasting the Use of Force: A Word Embedding Analysis of "
           "China's Rhetoric and Military Escalations*, Political Science Research and Methods.")
