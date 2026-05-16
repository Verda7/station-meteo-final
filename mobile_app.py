
import streamlit as st
import pandas as pd
import numpy as np
import requests

st.set_page_config(page_title="Météo Frasnes / Rèves Mobile", page_icon="🌦️", layout="centered", initial_sidebar_state="collapsed")

LAT = 50.5384
LON = 4.4523

HOURLY = [
    "temperature_2m","apparent_temperature","precipitation","precipitation_probability",
    "weather_code","cloud_cover","wind_speed_10m","wind_gusts_10m","wind_direction_10m",
    "relative_humidity_2m","dew_point_2m","pressure_msl","uv_index","cape","freezing_level_height"
]

def safe_float(x, default=0):
    try:
        if pd.isna(x):
            return default
        return float(x)
    except Exception:
        return default

def weather_text(code):
    try:
        code = int(code)
    except Exception:
        return "variable"
    mapping = {
        0:"ciel clair",1:"peu nuageux",2:"partiellement nuageux",3:"couvert",
        45:"brouillard",48:"brouillard givrant",51:"bruine faible",53:"bruine",55:"bruine forte",
        61:"pluie faible",63:"pluie",65:"pluie forte",80:"averses faibles",81:"averses",82:"averses fortes",
        95:"orage",96:"orage avec grêle",99:"orage violent avec grêle"
    }
    return mapping.get(code, "variable")

def icon_weather(code, precip=0, cloud=0, storm=0):
    code = int(safe_float(code, 3))
    precip = safe_float(precip)
    cloud = safe_float(cloud, 80)
    storm = safe_float(storm)
    if storm >= 70 or code in [95,96,99]:
        return "⛈️"
    if precip >= 2 or code in [63,65,81,82]:
        return "🌧️"
    if precip > 0.1 or code in [51,53,55,61,80]:
        return "🌦️"
    if code in [45,48]:
        return "🌫️"
    if cloud >= 80 or code == 3:
        return "☁️"
    if cloud >= 35 or code in [1,2]:
        return "⛅"
    return "☀️"

def risk_color(score):
    score = safe_float(score)
    if score < 20: return "#15803d"
    if score < 40: return "#ca8a04"
    if score < 60: return "#f97316"
    if score < 80: return "#dc2626"
    return "#7c3aed"

def risk_label(score):
    score = safe_float(score)
    if score < 20: return "Faible"
    if score < 40: return "À surveiller"
    if score < 60: return "Significatif"
    if score < 80: return "Fort"
    return "Sévère"

def deg_to_compass(deg):
    try:
        deg = float(deg) % 360
    except Exception:
        return ""
    dirs = ["N","NE","E","SE","S","SO","O","NO"]
    return dirs[int((deg + 22.5) // 45) % 8]

@st.cache_data(ttl=600)
def load_forecast():
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": LAT, "longitude": LON, "hourly": ",".join(HOURLY),
        "forecast_days": 8, "timezone": "Europe/Brussels", "wind_speed_unit": "kmh"
    }
    r = requests.get(url, params=params, timeout=25)
    r.raise_for_status()
    df = pd.DataFrame(r.json()["hourly"])
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

    d["score_orage"] = ((cape/30).clip(0,45) + (precip*8).clip(0,30) + ((gust-30)*0.7).clip(0,25) + ((humidity-55)*0.25).clip(0,10)).clip(0,100).round(1)
    d["score_pluie_intense"] = ((precip*15) + (proba*0.4)).clip(0,100).round(1)
    d["score_grele"] = ((cape/45).clip(0,45) + ((4500-freezing)/60).clip(0,25) + (gust/3).clip(0,30)).clip(0,100).round(1)
    d["score_tornade_approximatif"] = ((cape/80).clip(0,30) + ((gust-45)*0.8).clip(0,35) + ((dew-12)*2).clip(0,20)).clip(0,100).round(1)
    d["risque_downburst"] = (((gust-50)*1.2).clip(0,45) + ((temp-20)*1.2).clip(0,25) + ((100-humidity)*0.25).clip(0,20) + (cape/120).clip(0,10)).clip(0,100).round(1)
    d["risque_supercellule"] = ((cape/60).clip(0,35) + ((gust-45)*0.8).clip(0,35) + ((dew-12)*1.5).clip(0,20) + ((4500-freezing)/150).clip(0,10)).clip(0,100).round(1)
    return d

def css():
    st.markdown("""
<style>
.block-container {padding-top:1rem;padding-left:.75rem;padding-right:.75rem;max-width:520px;}
div[data-testid="stToolbar"] {display:none;}
.mobile-card {background:linear-gradient(160deg,#2563eb 0%,#1e3a8a 45%,#020617 100%);border-radius:28px;padding:22px;color:white;box-shadow:0 14px 32px rgba(0,0,0,.35);margin-bottom:16px;}
.alert-box {color:white;border-radius:22px;padding:14px 16px;font-weight:800;margin-bottom:18px;}
.small-card {background:#0f172a;border:1px solid #263244;color:white;border-radius:18px;padding:12px;text-align:center;margin-bottom:10px;}
.day-card {background:#0f172a;border:1px solid #263244;color:white;border-radius:18px;padding:14px;margin-bottom:10px;}
.pill {color:white;padding:5px 9px;border-radius:999px;font-weight:800;display:inline-block;font-size:12px;}
h1,h2,h3 {letter-spacing:-.03em;}
</style>
""", unsafe_allow_html=True)

def hero(df):
    row = df.iloc[0]
    storm = safe_float(row["score_orage"])
    icon = icon_weather(row["weather_code"], row["precipitation"], row["cloud_cover"], storm)
    st.markdown(f"""<div class="mobile-card"><div style="font-size:34px;font-weight:850;">Frasnes / Rèves</div><div style="opacity:.8;margin-bottom:15px;">Mis à jour : {pd.to_datetime(row["time"]).strftime("%d/%m/%Y %H:%M")}</div><div style="display:flex;align-items:center;justify-content:space-between;"><div><div style="font-size:66px;font-weight:900;line-height:.95;">{safe_float(row["temperature_2m"]):.1f}°</div><div style="font-size:16px;opacity:.9;">{row["temps"]} · ressenti {safe_float(row["apparent_temperature"]):.1f}°</div></div><div style="font-size:78px;">{icon}</div></div></div>""", unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f'<div class="small-card"><b>💧 Pluie</b><br><span style="font-size:22px;font-weight:850;">{safe_float(row["precipitation"]):.1f} mm</span></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="small-card"><b>💨 Vent</b><br><span style="font-size:22px;font-weight:850;">{safe_float(row["wind_speed_10m"]):.0f} km/h</span></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="small-card"><b>🌬️ Rafales</b><br><span style="font-size:22px;font-weight:850;">{safe_float(row["wind_gusts_10m"]):.0f} km/h</span></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="small-card"><b>⛈️ Orage</b><br><span style="font-size:22px;font-weight:850;">{storm:.0f}/100</span></div>', unsafe_allow_html=True)

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
    st.markdown(f"""<div class="alert-box" style="background:{color};">⚠️ Vigilance 24h : {label}<br><span style="font-size:13px;font-weight:600;">⛈️ {storm:.0f}/100 · 🌧️ {rain:.0f}/100 · 🧊 {hail:.0f}/100 · 🌀 {supercell:.0f}/100 · 💨 {gust:.0f} km/h</span></div>""", unsafe_allow_html=True)

def hourly(df):
    st.markdown("## ⏰ Heure par heure")
    rows = list(df.head(12).iterrows())
    for start in range(0, len(rows), 3):
        cols = st.columns(3)
        for col, (_, r) in zip(cols, rows[start:start+3]):
            storm = safe_float(r["score_orage"])
            color = risk_color(storm)
            icon = icon_weather(r["weather_code"], r["precipitation"], r["cloud_cover"], storm)
            with col:
                st.markdown(f"""<div class="small-card"><div style="opacity:.75;">{pd.to_datetime(r["time"]).strftime("%Hh")}</div><div style="font-size:34px;">{icon}</div><div style="font-size:26px;font-weight:850;">{safe_float(r["temperature_2m"]):.0f}°</div><div style="font-size:12px;">💧 {safe_float(r["precipitation"]):.1f} mm</div><div style="font-size:12px;">💨 {safe_float(r["wind_gusts_10m"]):.0f} km/h</div><div style="height:5px;background:{color};border-radius:999px;margin-top:8px;"></div></div>""", unsafe_allow_html=True)

def daily(df):
    st.markdown("## 📅 7 prochains jours")
    d = df.copy()
    d["date"] = pd.to_datetime(d["time"]).dt.date
    day_df = d.groupby("date", as_index=False).agg(
        temp_min=("temperature_2m","min"), temp_max=("temperature_2m","max"),
        rain=("precipitation","sum"), gust=("wind_gusts_10m","max"),
        storm=("score_orage","max"), code=("weather_code","first"), cloud=("cloud_cover","mean")
    ).head(7)
    for _, r in day_df.iterrows():
        storm = safe_float(r["storm"])
        color = risk_color(storm)
        label = risk_label(storm)
        icon = icon_weather(r["code"], r["rain"], r["cloud"], storm)
        st.markdown(f"""<div class="day-card"><div style="display:flex;align-items:center;justify-content:space-between;gap:8px;"><div style="min-width:65px;"><b>{pd.to_datetime(r["date"]).strftime("%a")}</b><br>{pd.to_datetime(r["date"]).strftime("%d/%m")}</div><div style="font-size:34px;">{icon}</div><div style="font-size:20px;font-weight:850;">{safe_float(r["temp_min"]):.0f}/{safe_float(r["temp_max"]):.0f}°</div><div>💧 {safe_float(r["rain"]):.1f}</div></div><div style="display:flex;align-items:center;justify-content:space-between;margin-top:10px;"><span>💨 {safe_float(r["gust"]):.0f} km/h</span><span>⛈️ {storm:.0f}/100</span><span class="pill" style="background:{color};">{label}</span></div></div>""", unsafe_allow_html=True)

def details(df):
    st.markdown("## 📊 Détails")
    r = df.iloc[0]
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Humidité", f"{safe_float(r['relative_humidity_2m']):.0f}%")
        st.metric("Point de rosée", f"{safe_float(r['dew_point_2m']):.1f}°C")
        st.metric("Pression", f"{safe_float(r['pressure_msl']):.1f} hPa")
    with c2:
        st.metric("UV", f"{safe_float(r['uv_index']):.1f}")
        st.metric("Direction", r["direction_vent"])
        st.metric("Supercellule", f"{safe_float(r['risque_supercellule']):.0f}/100")

css()
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
    st.caption("Version mobile V11.1 — scores indicatifs, ne remplace pas les alertes officielles.")
except Exception as e:
    st.error("Erreur de chargement météo.")
    st.exception(e)
