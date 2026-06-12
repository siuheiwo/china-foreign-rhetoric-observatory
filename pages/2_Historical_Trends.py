"""Page 2: Historical trends — annual averages 1950–2025 with event annotations."""
import pandas as pd
import plotly.express as px
import streamlit as st
from utils import load_scores, MEASURES, METHODOLOGY, WINDOW

st.set_page_config(page_title="Historical Trends · Observatory", layout="wide")
st.title("Historical trends, 1950–2025")

EVENTS = {1966: "Cultural Revolution", 1989: "Tiananmen",
          1996: "Taiwan Strait Crisis", 2022: "Pelosi visit"}

with st.sidebar:
    measure = st.selectbox("Index", list(MEASURES.keys()), format_func=lambda k: MEASURES[k])

df = load_scores("Monthly")
df["year"] = df["period"].dt.year
yearly = df.groupby(["country", "year"], as_index=False)[measure].mean()
yearly = yearly[(yearly["year"] >= 1950) & (yearly["year"] <= 2025)]

countries = sorted(yearly["country"].unique())
pick = st.multiselect("Countries", countries, default=["US", "Russia", "Japan"])
sub = yearly[yearly["country"].isin(pick)]

fig = px.line(sub, x="year", y=measure, color="country",
              labels={measure: MEASURES[measure], "year": ""})
for yr, name in EVENTS.items():
    fig.add_vline(x=yr, line_dash="dot", line_color="grey")
    fig.add_annotation(x=yr, y=1, yref="paper", text=name, showarrow=False,
                       textangle=-90, font=dict(size=10, color="grey"), xshift=-8, yanchor="top")
fig.update_layout(margin=dict(l=0, r=0, t=10, b=0), legend_title="")
st.plotly_chart(fig, use_container_width=True)

st.divider()
st.caption(f"**Methodology — {MEASURES[measure]}.** {METHODOLOGY[measure]}  "
           "Annual = mean of the monthly series (empty months scored 0).")
