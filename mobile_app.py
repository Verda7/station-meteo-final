
import streamlit as st
import pandas as pd
import requests

st.set_page_config(page_title="Frasnes / Rèves Mobile", page_icon="🌦️", layout="centered")

LAT = 50.5384
LON = 4.4523

@st.cache_data(ttl=600)
def load():
    r = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": LAT,
            "longitude": LON,
            "hourly": "temperature_2m,precipitation,weather_code,wind_speed_10m,wind_gusts_10m,relative_humidity_2m",
            "forecast_days": 7,
            "timezone": "Europe/Brussels",
            "wind_speed_unit": "kmh"
        },
        timeout=20
    )
    r.raise_for_status()
    data = r.json()["hourly"]
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"])
    return df

def icon(code):
    code = int(code)
    if code in [95,96,99]:
        return "⛈️"
    if code in [61,63,65,80,81,82]:
        return "🌧️"
    if code in [45,48]:
        return "🌫️"
    if code in [1,2]:
        return "⛅"
    if code == 3:
        return "☁️"
    return "☀️"

def level(score):
    if score < 35:
        return "VERT", "#15803d"
    if score < 55:
        return "JAUNE", "#ca8a04"
    if score < 75:
        return "ORANGE", "#f97316"
    return "ROUGE", "#dc2626"

st.markdown("""
<style>
.block-container {max-width:540px;padding-top:1rem;}
.hero {
background:linear-gradient(160deg,#2563eb 0%,#1e3a8a 50%,#020617 100%);
padding:22px;
border-radius:28px;
color:white;
margin-bottom:18px;
}
.card {
background:#0f172a;
border:1px solid #263244;
padding:14px;
border-radius:18px;
color:white;
text-align:center;
margin-bottom:10px;
}
.alert {
padding:16px;
border-radius:22px;
color:white;
font-weight:800;
margin-bottom:18px;
}
</style>
""", unsafe_allow_html=True)

try:
    df = load()
    now = df.iloc[0]

    rain = min(float(now["precipitation"]) * 25, 100)
    gust = float(now["wind_gusts_10m"])
    storm = min((rain * 0.7) + max(gust - 30, 0), 100)

    code_txt, color = level(storm)

    st.markdown(f"""
    <div class="hero">
    <div style="font-size:34px;font-weight:900;">Frasnes / Rèves</div>
    <div style="opacity:.8;">Prévision mobile ultra stable</div>

    <div style="display:flex;justify-content:space-between;align-items:center;margin-top:18px;">
        <div>
            <div style="font-size:74px;font-weight:900;">
                {float(now["temperature_2m"]):.1f}°C
            </div>

            <div style="font-size:22px;">
                Humidité {float(now["relative_humidity_2m"]):.0f}%
            </div>
        </div>

        <div style="font-size:86px;">
            {icon(now["weather_code"])}
        </div>
    </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="alert" style="background:{color};">
    ⚠️ CODE {code_txt}<br>
    Orage {storm:.0f}/100 • Rafales {gust:.0f} km/h
    </div>
    """, unsafe_allow_html=True)

    st.markdown("## 🌅 Matin • Après-midi • Soirée")

    cols = st.columns(3)
    periods = [("Matin","☀️"),("Après-midi","🌦️"),("Soirée","☁️")]

    for col, item in zip(cols, periods):
        name, emo = item
        with col:
            st.markdown(f"""
            <div class="card">
            <div style="font-size:28px;">{emo}</div>
            <b>{name}</b><br><br>
            {float(now["temperature_2m"]):.0f}°C
            </div>
            """, unsafe_allow_html=True)

    st.markdown("## ⏰ Prochaines heures")

    rows = list(df.head(9).iterrows())

    for start in range(0, len(rows), 3):
        cols = st.columns(3)

        for col, (_, r) in zip(cols, rows[start:start+3]):
            with col:
                st.markdown(f"""
                <div class="card">
                <b>{pd.to_datetime(r["time"]).strftime("%Hh")}</b><br><br>
                <div style="font-size:32px;">{icon(r["weather_code"])}</div>
                <div style="font-size:28px;font-weight:900;">
                {float(r["temperature_2m"]):.0f}°
                </div>

                💧 {float(r["precipitation"]):.1f} mm<br>
                💨 {float(r["wind_gusts_10m"]):.0f} km/h
                </div>
                """, unsafe_allow_html=True)

    st.markdown("## 🌧️ Radar")
    st.link_button("📡 Ouvrir radar Windy", "https://www.windy.com/50.538/4.452")

except Exception as e:
    st.error("Erreur météo")
    st.code(str(e))
