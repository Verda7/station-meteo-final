import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import random

st.set_page_config(page_title="Station Météo Frasnes / Rèves", layout="wide")

st.title("🌦️ Station Météo — Frasnes / Rèves")

tabs = st.tabs([
    "📱 Interface App",
    "📈 Résumé"
])

def risk_color(score):
    if score < 20:
        return "#16a34a"
    if score < 40:
        return "#eab308"
    if score < 60:
        return "#f97316"
    if score < 80:
        return "#dc2626"
    return "#7e22ce"

with tabs[0]:

    temp = round(random.uniform(8,16),1)
    rain = round(random.uniform(0,3),1)
    wind = random.randint(10,35)
    gust = random.randint(20,60)
    storm = random.randint(5,45)

    st.markdown(f"""
    <div style="
        background:linear-gradient(135deg,#2563eb,#0f172a);
        padding:30px;
        border-radius:25px;
        color:white;
        margin-bottom:20px;
    ">
        <h1 style="margin:0;">Frasnes / Rèves</h1>
        <p style="opacity:0.8;">Prévision multi-modèles</p>

        <div style="display:flex;justify-content:space-between;align-items:center;">
            <div>
                <h1 style="font-size:70px;">{temp}°C</h1>
                <h3>🌧️ Pluie : {rain} mm</h3>
                <h3>💨 Vent : {wind} km/h</h3>
                <h3>🌬️ Rafales : {gust} km/h</h3>
            </div>
            <div style="font-size:100px;">⛅</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div style="
        background:{risk_color(storm)};
        color:white;
        padding:15px;
        border-radius:15px;
        font-size:22px;
        font-weight:bold;
        margin-bottom:20px;
    ">
        ⚠️ Score orage : {storm}/100
    </div>
    """, unsafe_allow_html=True)

    st.subheader("⏰ Prochaines heures")

    cols = st.columns(6)

    for i,col in enumerate(cols):
        hour = (datetime.now() + timedelta(hours=i)).strftime("%H:%M")
        t = round(temp + random.uniform(-2,2),1)
        p = round(random.uniform(0,2),1)

        with col:
            st.markdown(f"""
            <div style="
                background:#111827;
                color:white;
                padding:15px;
                border-radius:18px;
                text-align:center;
            ">
                <h3>{hour}</h3>
                <div style="font-size:40px;">🌦️</div>
                <h2>{t}°</h2>
                <p>💧 {p} mm</p>
            </div>
            """, unsafe_allow_html=True)

with tabs[1]:
    st.subheader("Résumé météo")
    st.write("Version V10 propre corrigée.")
