import streamlit as st
import pandas as pd
import numpy as np
import requests
from datetime import datetime

st.set_page_config(
    page_title="Météo Frasnes / Rèves Mobile",
    page_icon="🌦️",
    layout="centered",
    initial_sidebar_state="collapsed"
)

LAT = 50.5384
LON = 4.4523

HOURLY = [
    "temperature_2m",
    "apparent_temperature",
    "precipitation",
    "precipitation_probability",
    "weather_code",
    "cloud_cover",
    "wind_speed_10m",
    "wind_gusts_10m",
    "wind_direction_10m",
    "relative_humidity_2m",
    "dew_point_2m",
    "pressure_msl",
    "uv_index",
    "cape",
    "freezing_level_height",
]

def weather_text(code):
    try:
        code = int(code)
    except Exception:
        return "variable"

    mapping = {
        0: "ciel clair",
        1: "peu nuageux",
        2: "partiellement nuageux",
        3: "couvert",
        45: "brouillard",
        48: "brouillard givrant",
        51: "bruine faible",
        53: "bruine",
        55: "bruine forte",
        61: "pluie faible",
        63: "pluie",
        65: "pluie forte",
        71: "neige faible",
        73: "neige",
        75: "neige forte",
        80: "averses faibles",
        81: "averses",
        82: "averses fortes",
        95: "orage",
        96: "orage avec grêle",
        99: "orage violent avec grêle",
    }
    return mapping.get(code, "variable")

def icon_weather(code, precip=0, cloud=0, storm=0):
    try:
        code = int(code)
        precip = float(precip)
        cloud = float(cloud)
        storm = float(storm)
    except Exception:
        code, precip, cloud, storm = 3, 0, 80, 0

    if storm >= 70 or code in [95, 96, 99]:
        return "⛈️"
    if precip >= 2 or code in [63, 65, 81, 82]:
        return "🌧️"
    if precip > 0.1 or code in [51, 53, 55, 61, 80]:
        return "🌦️"
    if code in [45, 48]:
        return "🌫️"
    if cloud >= 80 or code == 3:
        return "☁️"
    if cloud >= 35 or code in [1, 2]:
        return "⛅"
    return "☀️"

def risk_color(score):
    try:
        score = float(score)
    except Exception:
        score = 0
    if score < 20:
        return "#15803d"
    if score < 40:
        return "#ca8a04"
    if score < 60:
        return "#f97316"
    if score < 80:
        return "#dc2626"
    return "#7c3aed"

def risk_label(score):
    try:
        score = float(score)
    except Exception:
        score = 0
    if score < 20:
        return "Faible"
    if score < 40:
        return "À surveiller"
    if score < 60:
        return "Significatif"
    if score < 80:
        return "Fort"
    return "Sévère"

def deg_to_compass(deg):
    try:
        if pd.isna(deg):
            return ""
        deg = float(deg) % 360
    except Exception:
        return ""
    dirs = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
    return dirs[int((deg + 22.5) // 45) % 8]

def safe_float(x, default=0):
    try:
        if pd.isna(x):
            return default
        return float(x)
    except Exception:
        return default

@st.cache_data(ttl=600)
def load_forecast():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": LAT,
        "longitude": LON,
        "hourly": ",".join(HOURLY),
        "forecast_days": 8,
        "timezone": "Europe/Brussels",
        "wind_speed_unit": "kmh",
    }

    r = requests.get(url, params=params, timeout=25)
    r.raise_for_status()
    data = r.json()["hourly"]

    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"])

    for col in HOURLY:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["temps"] = df["weather_code"].apply(weather_text)
    df["direction_vent"] = df["wind_direction_10m"].apply(deg_to_compass)

    return compute_scores(df)

def compute_scores(df):
    d = df.copy()

    cape = d.get("cape", pd.Series(0, index=d.index)).fillna(0)
    precip = d.get("precipitation", pd.Series(0, index=d.index)).fillna(0)
    proba = d.get("precipitation_probability", pd.Series(0, index=d.index)).fillna(0)
    gust = d.get("wind_gusts_10m", pd.Series(0, index=d.index)).fillna(0)
    humidity = d.get("relative_humidity_2m", pd.Series(0, index=d.index)).fillna(0)
    dew = d.get("dew_point_2m", pd.Series(0, index=d.index)).fillna(0)
    temp = d.get("temperature_2m", pd.Series(0, index=d.index)).fillna(0)
    freezing = d.get("freezing_level_height", pd.Series(2500, index=d.index)).replace(0, np.nan).fillna(2500)

    d["score_orage"] = (
        (cape / 30).clip(0, 45)
        + (precip * 8).clip(0, 30)
        + ((gust - 30) * 0.7).clip(0, 25)
        + ((humidity - 55) * 0.25).clip(0, 10)
    ).clip(0, 100).round(1)

    d["score_pluie_intense"] = ((precip * 15) + (proba * 0.4)).clip(0, 100).round(1)

    d["score_grele"] = (
        (cape / 45).clip(0, 45)
        + ((4500 - freezing) / 60).clip(0, 25)
        + (gust / 3).clip(0, 30)
    ).clip(0, 100).round(1)

    d["score_tornade_approximatif"] = (
        (cape / 80).clip(0, 30)
        + ((gust - 45) * 0.8).clip(0, 35)
        + ((dew - 12) * 2).clip(0, 20)
    ).clip(0, 100).round(1)

    d["risque_downburst"] = (
        ((gust - 50) * 1.2).clip(0, 45)
        + ((temp - 20) * 1.2).clip(0, 25)
        + ((100 - humidity) * 0.25).clip(0, 20)
        + (cape / 120).clip(0, 10)
    ).clip(0, 100).round(1)

    d["risque_supercellule"] = (
        (cape / 60).clip(0, 35)
        + ((gust - 45) * 0.8).clip(0, 35)
        + ((dew - 12) * 1.5).clip(0, 20)
        + ((4500 - freezing) / 150).clip(0, 10)
    ).clip(0, 100).round(1)

    return d

def app_css():
    st.markdown("""
    <style>
    .block-container {
        padding-top: 1.2rem;
        padding-left: 0.8rem;
        padding-right: 0.8rem;
        max-width: 540px;
    }

    .hero {
        background: linear-gradient(160deg, #2563eb 0%, #1e3a8a 50%, #020617 100%);
        border-radius: 30px;
        padding: 24px;
        color: white;
        box-shadow: 0 16px 35px rgba(0,0,0,.35);
        margin-bottom: 16px;
    }

    .place {
        font-size: 28px;
        font-weight: 800;
        margin-bottom: 3px;
    }

    .updated {
        opacity: .80;
        font-size: 13px;
        margin-bottom: 14px;
    }

    .main-grid {
        display: grid;
        grid-template-columns: 1.15fr 0.85fr;
        gap: 12px;
        align-items: center;
    }

    .temp {
        font-size: 68px;
        font-weight: 850;
        line-height: .95;
    }

    .weather-icon {
        font-size: 86px;
        text-align: right;
    }

    .desc {
        font-size: 17px;
        opacity: .92;
        margin-top: 6px;
    }

    .mini-grid {
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        gap: 9px;
        margin-top: 18px;
    }

    .mini {
        background: rgba(255,255,255,.13);
        border: 1px solid rgba(255,255,255,.18);
        border-radius: 18px;
        padding: 11px;
        text-align: center;
    }

    .mini b {
        font-size: 12px;
        opacity: .85;
    }

    .mini div {
        font-size: 18px;
        font-weight: 800;
        margin-top: 4px;
    }

    .alert {
        color: white;
        border-radius: 22px;
        padding: 14px 16px;
        font-weight: 800;
        margin-bottom: 18px;
        box-shadow: 0 10px 25px rgba(0,0,0,.20);
    }

    .section-title {
        font-size: 22px;
        font-weight: 850;
        margin: 16px 0 10px 0;
    }

    .hour-wrap {
        display: flex;
        overflow-x: auto;
        gap: 10px;
        padding-bottom: 8px;
        margin-bottom: 8px;
    }

    .hour {
        min-width: 86px;
        background: #0f172a;
        color: white;
        border: 1px solid #263244;
        border-radius: 20px;
        padding: 12px 8px;
        text-align: center;
    }

    .hour-time {
        opacity: .8;
        font-size: 13px;
    }

    .hour-icon {
        font-size: 30px;
        margin: 5px 0;
    }

    .hour-temp {
        font-size: 22px;
        font-weight: 850;
    }

    .hour-small {
        font-size: 12px;
        opacity: .9;
    }

    .risk-bar {
        height: 5px;
        border-radius: 99px;
        margin-top: 7px;
    }

    .day {
        display: grid;
        grid-template-columns: 72px 42px 78px 72px 72px 1fr;
        gap: 6px;
        align-items: center;
        background: #0f172a;
        border: 1px solid #263244;
        color: white;
        border-radius: 18px;
        padding: 10px;
        margin-bottom: 8px;
        font-size: 13px;
    }

    .pill {
        color: white;
        padding: 5px 8px;
        border-radius: 999px;
        font-weight: 800;
        text-align: center;
        font-size: 12px;
    }

    .metric-card {
        background: #0f172a;
        border: 1px solid #263244;
        color: white;
        border-radius: 18px;
        padding: 12px;
        margin-bottom: 8px;
    }

    .metric-label {
        opacity: .75;
        font-size: 12px;
    }

    .metric-value {
        font-size: 22px;
        font-weight: 850;
    }

    @media (max-width: 430px) {
        .temp { font-size: 58px; }
        .weather-icon { font-size: 70px; }
        .place { font-size: 24px; }
        .day { grid-template-columns: 62px 34px 70px 62px; }
    }
    </style>
    """, unsafe_allow_html=True)

def hero(df):
    row = df.iloc[0]
    storm = safe_float(row.get("score_orage"))
    icon = icon_weather(
        row.get("weather_code"),
        row.get("precipitation"),
        row.get("cloud_cover"),
        storm
    )

    st.markdown(f"""
    <div class="hero">
        <div class="place">Frasnes / Rèves</div>
        <div class="updated">Mis à jour : {pd.to_datetime(row["time"]).strftime("%d/%m/%Y %H:%M")}</div>

        <div class="main-grid">
            <div>
                <div class="temp">{safe_float(row.get("temperature_2m")):.1f}°</div>
                <div class="desc">{row.get("temps","variable")} · ressenti {safe_float(row.get("apparent_temperature")):.1f}°</div>
            </div>
            <div class="weather-icon">{icon}</div>
        </div>

        <div class="mini-grid">
            <div class="mini"><b>Pluie</b><div>{safe_float(row.get("precipitation")):.1f} mm</div></div>
            <div class="mini"><b>Vent</b><div>{safe_float(row.get("wind_speed_10m")):.0f} km/h</div></div>
            <div class="mini"><b>Rafales</b><div>{safe_float(row.get("wind_gusts_10m")):.0f} km/h</div></div>
            <div class="mini"><b>Orage</b><div>{storm:.0f}/100</div></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

def alert_banner(df):
    next24 = df.head(24)
    storm = safe_float(next24["score_orage"].max())
    rain = safe_float(next24["score_pluie_intense"].max())
    hail = safe_float(next24["score_grele"].max())
    supercell = safe_float(next24["risque_supercellule"].max())
    gust = safe_float(next24["wind_gusts_10m"].max())
    max_score = max(storm, rain, hail, supercell)
    color = risk_color(max_score)
    label = risk_label(max_score)

    st.markdown(f"""
    <div class="alert" style="background:{color};">
        ⚠️ Vigilance 24h : {label}<br>
        <span style="font-size:13px;font-weight:600;">
        ⛈️ {storm:.0f}/100 · 🌧️ {rain:.0f}/100 · 🧊 {hail:.0f}/100 · 🌀 {supercell:.0f}/100 · 💨 {gust:.0f} km/h
        </span>
    </div>
    """, unsafe_allow_html=True)

def hourly(df):
    st.markdown('<div class="section-title">⏰ Heure par heure</div>', unsafe_allow_html=True)

    cards = []
    for _, r in df.head(16).iterrows():
        storm = safe_float(r.get("score_orage"))
        color = risk_color(storm)
        icon = icon_weather(
            r.get("weather_code"),
            r.get("precipitation"),
            r.get("cloud_cover"),
            storm
        )

        cards.append(f"""
        <div class="hour">
            <div class="hour-time">{pd.to_datetime(r["time"]).strftime("%Hh")}</div>
            <div class="hour-icon">{icon}</div>
            <div class="hour-temp">{safe_float(r.get("temperature_2m")):.0f}°</div>
            <div class="hour-small">💧 {safe_float(r.get("precipitation")):.1f} mm</div>
            <div class="hour-small">💨 {safe_float(r.get("wind_gusts_10m")):.0f}</div>
            <div class="risk-bar" style="background:{color};"></div>
        </div>
        """)

    st.markdown('<div class="hour-wrap">' + "".join(cards) + "</div>", unsafe_allow_html=True)

def daily(df):
    st.markdown('<div class="section-title">📅 7 prochains jours</div>', unsafe_allow_html=True)

    d = df.copy()
    d["date"] = pd.to_datetime(d["time"]).dt.date

    day_df = d.groupby("date", as_index=False).agg(
        temp_min=("temperature_2m", "min"),
        temp_max=("temperature_2m", "max"),
        rain=("precipitation", "sum"),
        gust=("wind_gusts_10m", "max"),
        storm=("score_orage", "max"),
        code=("weather_code", "first"),
        cloud=("cloud_cover", "mean")
    ).head(7)

    for _, r in day_df.iterrows():
        storm = safe_float(r.get("storm"))
        color = risk_color(storm)
        label = risk_label(storm)
        icon = icon_weather(
            r.get("code"),
            r.get("rain"),
            r.get("cloud"),
            storm
        )

        st.markdown(f"""
        <div class="day">
            <div><b>{pd.to_datetime(r["date"]).strftime("%a")}</b><br>{pd.to_datetime(r["date"]).strftime("%d/%m")}</div>
            <div style="font-size:27px;">{icon}</div>
            <div><b>{safe_float(r["temp_min"]):.0f}/{safe_float(r["temp_max"]):.0f}°</b></div>
            <div>💧 {safe_float(r["rain"]):.1f}</div>
            <div>💨 {safe_float(r["gust"]):.0f}</div>
            <div class="pill" style="background:{color};">{label}</div>
        </div>
        """, unsafe_allow_html=True)

def details(df):
    st.markdown('<div class="section-title">📊 Détails rapides</div>', unsafe_allow_html=True)

    r = df.iloc[0]

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Humidité</div>
            <div class="metric-value">{safe_float(r.get("relative_humidity_2m")):.0f}%</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Point de rosée</div>
            <div class="metric-value">{safe_float(r.get("dew_point_2m")):.1f}°C</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Pression</div>
            <div class="metric-value">{safe_float(r.get("pressure_msl")):.1f} hPa</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">UV</div>
            <div class="metric-value">{safe_float(r.get("uv_index")):.1f}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Direction vent</div>
            <div class="metric-value">{r.get("direction_vent","")}</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">Supercellule</div>
            <div class="metric-value">{safe_float(r.get("risque_supercellule")):.0f}/100</div>
        </div>
        """, unsafe_allow_html=True)

# MAIN
app_css()

try:
    df = load_forecast()
    now = pd.Timestamp.now(tz="Europe/Brussels").tz_localize(None)
    df = df[df["time"] >= now].copy()
    if df.empty:
        st.error("Aucune donnée météo disponible.")
        st.stop()

    hero(df)
    alert_banner(df)
    hourly(df)
    daily(df)
    details(df)

    st.caption("Version mobile dédiée — données Open-Meteo. Les scores sont indicatifs et ne remplacent pas les alertes officielles.")
except Exception as e:
    st.error("Erreur de chargement météo.")
    st.exception(e)
