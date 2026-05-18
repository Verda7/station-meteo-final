
import plotly.express as px

st.markdown("### 📈 Température & Ressenti")

graph_df = df.copy().head(48)

fig = px.line(
    graph_df,
    x="time",
    y=["temperature_2m", "apparent_temperature"],
)

fig.update_layout(
    height=320,
    margin=dict(l=10, r=10, t=30, b=10),
    legend_title_text="",
)

st.plotly_chart(fig, use_container_width=True)
