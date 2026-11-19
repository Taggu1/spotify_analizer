import os

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy import create_engine, text

GREEN = "#1DB954"
GREEN_DIM = "#1E5C37"
MUTED = "#B3B3B3"
TZ = "Africa/Cairo"

# Timestamp column in streaming_history_normalized (change if yours differs)
PLATFORM_TS_COL = "played_at"

st.set_page_config(page_title="My Spotify", page_icon="🎧", layout="wide")

# ---------- Global CSS ----------
st.markdown(
    """
    <style>
      #MainMenu, footer, header {visibility: hidden;}
      .block-container {padding-top: 1.5rem; max-width: 1200px;}

      /* Cards */
      [data-testid="stVerticalBlockBorderWrapper"] {
          background: #181818;
          border: 1px solid #282828;
          border-radius: 14px;
          padding: 0.5rem;
      }

      /* KPIs */
      [data-testid="stMetricValue"] {
          color: #1DB954; font-size: 2rem; font-weight: 700;
      }
      [data-testid="stMetricLabel"] {
          color: #B3B3B3; text-transform: uppercase;
          letter-spacing: .08em; font-size: .75rem;
      }

      h1 {font-weight: 800; letter-spacing: -0.02em;}
      h3 {font-weight: 700;}
    </style>
    """,
    unsafe_allow_html=True,
)

engine = create_engine(os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg2://spotify:spotify@localhost:5433/spotify",
))


@st.cache_data(ttl=60)
def load(query, params=None):
    return pd.read_sql(text(query), engine, params=params or {})


def style(fig, height=320, color=GREEN):
    """One consistent look for every chart."""
    if color is not None:
        fig.update_traces(marker_color=color)
    fig.update_layout(
        height=height,
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=MUTED,
        showlegend=False,
        bargap=0.25,
        hoverlabel=dict(bgcolor="#282828", font_color="white"),
        xaxis=dict(showgrid=False, title=None),
        yaxis=dict(gridcolor="#2A2A2A", title=None),
    )
    fig.update_yaxes(zeroline=False)
    return fig


# ---------- Year filter ----------
years = load(f"""
    SELECT DISTINCT EXTRACT(YEAR FROM played_at AT TIME ZONE '{TZ}')::int AS y
    FROM listens ORDER BY y DESC
""")["y"].tolist()

st.title("🎧 My Spotify")

options = ["All time"] + years
if hasattr(st, "segmented_control"):
    choice = st.segmented_control(
        "Year", options, default="All time", label_visibility="collapsed"
    ) or "All time"
else:  # older Streamlit versions
    choice = st.selectbox("Year", options)

if choice == "All time":
    where, params = "", {}
    p_where = ""
else:
    where = f"WHERE EXTRACT(YEAR FROM played_at AT TIME ZONE '{TZ}') = :year"
    p_where = (
        f"WHERE EXTRACT(YEAR FROM {PLATFORM_TS_COL} AT TIME ZONE '{TZ}') = :year"
    )
    params = {"year": int(choice)}

st.caption(f"Listening history: {choice}")

# ---------- KPIs ----------
k = load(f"""
    SELECT COUNT(*) AS plays,
           COUNT(DISTINCT track_id) AS tracks,
           COUNT(DISTINCT artist_name) AS artists,
           COALESCE(SUM(ms_played), 0) / 3600000.0 AS hours
    FROM listens {where}
""", params).iloc[0]

if int(k["plays"]) == 0:
    st.warning("No listens found for this period.")
    st.stop()

top = load(f"""
    SELECT artist_name, COUNT(*) AS plays
    FROM listens {where}
    GROUP BY 1 ORDER BY 2 DESC LIMIT 10
""", params)

hourly = load(f"""
    SELECT EXTRACT(HOUR FROM played_at AT TIME ZONE '{TZ}')::int AS hour,
           COUNT(*) AS plays
    FROM listens {where} GROUP BY 1 ORDER BY 1
""", params)
# make sure all 24 hours are present
hourly = (
    hourly.set_index("hour").reindex(range(24), fill_value=0)
    .rename_axis("hour").reset_index()
)
peak_hour = int(hourly.loc[hourly["plays"].idxmax(), "hour"])

kpis = [
    ("Listens", f"{int(k['plays']):,}"),
    ("Different tracks", f"{int(k['tracks']):,}"),
    ("Different artists", f"{int(k['artists']):,}"),
    ("Hours listened", f"{k['hours']:,.0f}"),
    ("Top artist", str(top.iloc[0]["artist_name"])),
    ("Peak hour", f"{peak_hour:02d}:00"),
]
for col, (label, value) in zip(st.columns(len(kpis)), kpis):
    with col.container(border=True):
        st.metric(label, value)

# ---------- Over time ----------
with st.container(border=True):
    st.subheader("Listening over time")
    monthly = load(f"""
        SELECT date_trunc('month', played_at AT TIME ZONE '{TZ}')::date AS month,
               COUNT(*) AS plays
        FROM listens {where} GROUP BY 1 ORDER BY 1
    """, params)
    fig = px.area(monthly, x="month", y="plays")
    fig = style(fig, color=None)
    fig.update_traces(
        line_color=GREEN, line_width=3, line_shape="spline",
        fillcolor="rgba(29,185,84,0.25)",
    )
    st.plotly_chart(fig, use_container_width=True)

# ---------- Artists + hours ----------
left, right = st.columns(2)

with left:
    with st.container(border=True):
        st.subheader("Top artists")
        top_sorted = top.sort_values("plays")  # biggest ends up on top
        fig = px.bar(top_sorted, x="plays", y="artist_name",
                     orientation="h", text="plays")
        fig = style(fig, 380)
        fig.update_traces(textposition="outside", cliponaxis=False)
        fig.update_xaxes(range=[0, top_sorted["plays"].max() * 1.15])
        st.plotly_chart(fig, use_container_width=True)

with right:
    with st.container(border=True):
        st.subheader("When you listen (Cairo time)")
        fig = px.bar(hourly, x="hour", y="plays")
        fig = style(fig, 380, color=None)
        peak = hourly["plays"].max()
        fig.update_traces(
            marker_color=[GREEN if p == peak else GREEN_DIM for p in hourly["plays"]]
        )
        fig.update_xaxes(dtick=2)
        st.plotly_chart(fig, use_container_width=True)

# ---------- Top tracks + platforms ----------
left, right = st.columns([3, 2])

with left:
    with st.container(border=True):
        st.subheader("Top tracks")
        tracks = load(f"""
            SELECT track_name AS "Track", artist_name AS "Artist", COUNT(*) AS "Plays"
            FROM listens {where}
            GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 10
        """, params)
        st.dataframe(
            tracks,
            hide_index=True,
            use_container_width=True,
            column_config={
                "Plays": st.column_config.ProgressColumn(
                    "Plays",
                    format="%d",
                    min_value=0,
                    max_value=int(tracks["Plays"].max()),
                )
            },
        )

with right:
    with st.container(border=True):
        st.subheader("Listening by platform")
        try:
            platforms = load(f"""
                SELECT normalized_platform AS "platform", COUNT(*) AS "plays"
                FROM streaming_history_normalized {p_where}
                GROUP BY 1 ORDER BY 2 DESC
            """, params)
            fig = px.pie(
                platforms, names="platform", values="plays", hole=0.6,
                color_discrete_sequence=[
                    "#1DB954", "#1ED760", "#169C46", "#0F6B30", "#535353",
                ],
            )
            fig.update_traces(textinfo="percent", marker_line_width=0)
            fig.update_layout(
                height=380,
                margin=dict(l=0, r=0, t=10, b=0),
                paper_bgcolor="rgba(0,0,0,0)",
                font_color=MUTED,
                showlegend=True,
                legend=dict(orientation="h", y=-0.05),
                hoverlabel=dict(bgcolor="#282828", font_color="white"),
            )
            st.plotly_chart(fig, use_container_width=True)
        except Exception as e:
            st.info(
                "Couldn't load platform data. Check that "
                f"`streaming_history_normalized` has a `{PLATFORM_TS_COL}` column."
            )
            st.caption(str(e).splitlines()[0])


# ---------- Calendar heatmap ----------
with st.container(border=True):
    st.subheader("Listening calendar")
    daily = load(f"""
        SELECT (played_at AT TIME ZONE '{TZ}')::date AS day, COUNT(*) AS plays
        FROM listens {where} GROUP BY 1 ORDER BY 1
    """, params)
    daily["day"] = pd.to_datetime(daily["day"])

    if choice == "All time":  # last 12 months of data
        end = daily["day"].max()
        start = end - pd.Timedelta(days=364)
    else:
        start = pd.Timestamp(int(choice), 1, 1)
        end = pd.Timestamp(int(choice), 12, 31)

    cal = pd.DataFrame({"day": pd.date_range(start, end)})
    cal = cal.merge(daily, on="day", how="left").fillna({"plays": 0})
    cal["dow"] = cal["day"].dt.dayofweek  # Monday = 0
    first_monday = start - pd.Timedelta(days=start.dayofweek)
    cal["week"] = (cal["day"] - first_monday).dt.days // 7

    z = cal.pivot(index="dow", columns="week", values="plays")
    dates = cal.pivot(index="dow", columns="week", values="day").apply(
        lambda col: col.dt.strftime("%a, %d %b %Y")
    )
    month_ticks = cal[cal["day"].dt.day == 1]

    fig = go.Figure(go.Heatmap(
        z=z.values,
        x=z.columns,
        y=["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
        customdata=dates.values,
        hovertemplate="%{customdata}<br>%{z:.0f} plays<extra></extra>",
        xgap=3, ygap=3, zmin=0,
        colorscale=[
            [0.0, "#242424"], [0.0001, "#0E4429"],
            [0.5, "#169C46"], [1.0, "#1ED760"],
        ],
        showscale=False,
    ))
    fig.update_layout(
        height=230,
        margin=dict(l=0, r=0, t=10, b=0),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font_color=MUTED,
        hoverlabel=dict(bgcolor="#282828", font_color="white"),
        xaxis=dict(
            tickmode="array",
            tickvals=month_ticks["week"].tolist(),
            ticktext=month_ticks["day"].dt.strftime("%b").tolist(),
            showgrid=False, zeroline=False, side="top",
        ),
        yaxis=dict(autorange="reversed", showgrid=False, zeroline=False),
    )
    st.plotly_chart(fig, use_container_width=True)

    active = (cal["plays"] > 0).astype(int)
    longest = int(active.groupby((active == 0).cumsum()).cumsum().max())
    busiest = cal.loc[cal["plays"].idxmax()]
    st.caption(
        f"{int(active.sum())} active days  ·  longest streak: {longest} days  ·  "
        f"busiest day: {busiest['day']:%d %b %Y} ({int(busiest['plays']):,} plays)"
    )

# ---------- Artist loyalty ----------
MIN_PLAYS = 10  # ignore artists with fewer plays than this

with st.container(border=True):
    st.subheader("Artist loyalty")
    st.caption(
        "Each dot is an artist. Dots far above the line are artists where "
        "you replay the same few songs."
    )
    loyalty = load(f"""
        SELECT artist_name,
               COUNT(*) AS plays,
               COUNT(DISTINCT track_id) AS tracks
        FROM listens {where}
        GROUP BY 1
        HAVING COUNT(*) >= {MIN_PLAYS}
    """, params)

    if len(loyalty) < 5:
        st.info("Not enough artists with enough plays to draw this chart.")
    else:
        lx, ly = np.log10(loyalty["tracks"]), np.log10(loyalty["plays"])
        slope, intercept = np.polyfit(lx, ly, 1)
        loyalty["resid"] = ly - (slope * lx + intercept)
        loyalty["plays_per_track"] = (loyalty["plays"] / loyalty["tracks"]).round(1)

        fig = px.scatter(
            loyalty, x="tracks", y="plays", hover_name="artist_name",
            hover_data={"plays_per_track": True, "resid": False},
            log_x=True, log_y=True,
        )
        fig = style(fig, 440, color=None)
        fig.update_traces(marker=dict(
            color=GREEN, size=9, opacity=0.7,
            line=dict(width=0),
        ))

        xs = np.linspace(lx.min(), lx.max(), 50)
        fig.add_trace(go.Scatter(
            x=10 ** xs, y=10 ** (slope * xs + intercept),
            mode="lines", line=dict(color="#535353", dash="dot", width=2),
            hoverinfo="skip",
        ))

        for _, r in loyalty.nlargest(8, "resid").iterrows():
            fig.add_annotation(
                x=np.log10(r["tracks"]), y=np.log10(r["plays"]),
                text=r["artist_name"], showarrow=False,
                yshift=12, font=dict(color="#FFFFFF", size=11),
            )

        fig.update_xaxes(title="Different tracks played", gridcolor="#2A2A2A")
        fig.update_yaxes(title="Total plays")
        st.plotly_chart(fig, use_container_width=True)