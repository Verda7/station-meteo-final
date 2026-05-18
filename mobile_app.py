
import streamlit as st
import pandas as pd
import numpy as np
import requests

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

PERIODES = [
    ("🌅 Matin", 6, 12),
    ("🌤️ Après-midi", 12, 18),
    ("🌆 Soirée", 18, 24),
    ("🌙 Nuit", 0, 6),
]

def fnum(x, default=0):
    try:
        if pd.isna(x):
            return default
        return float(x)
    except Exception:
        return default

def compass(deg):
    try:
        deg = float(deg) % 360
    except Exception:
        return ""
    dirs = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
    return dirs[int((deg + 22.5) // 45) % 8]

def weather_text(code):
    c = int(fnum(code, 3))
    return {
        0: "Ciel clair",
        1: "Peu nuageux",
        2: "Partiellement nuageux",
        3: "Couvert",
        45: "Brume / brouillard",
        48: "Brouillard givrant",
        51: "Bruine faible",
        53: "Bruine",
        55: "Bruine forte",
        61: "Pluie faible",
        63: "Pluie",
        65: "Pluie forte",
        71: "Neige faible",
        73: "Neige",
        75: "Neige forte",
        80: "Averses faibles",
        81: "Averses",
        82: "Averses fortes",
        95: "Orage",
        96: "Orage avec grêle",
        99: "Orage violent",
    }.get(c, "Variable")

def fog_possible(row):
    c = int(fnum(row.get("weather_code", 0)))
    hum = fnum(row.get("relative_humidity_2m", 0))
    wind = fnum(row.get("wind_speed_10m", 0))
    temp = fnum(row.get("temperature_2m", 0))
    dew = fnum(row.get("dew_point_2m", 0))
    return c in [45, 48] or (hum >= 94 and abs(temp - dew) <= 1.6 and wind <= 12)

def icon_for(row, storm=0):
    c = int(fnum(row.get("weather_code", 3)))
    rain = fnum(row.get("precipitation", 0))
    cloud = fnum(row.get("cloud_cover", 80))

    if fog_possible(row):
        return "🌫️"
    if fnum(storm) >= 78 or c in [95, 96, 99]:
        return "⛈️"
    if rain >= 2 or c in [63, 65, 81, 82]:
        return "🌧️"
    if rain > 0.1 or c in [51, 53, 55, 61, 80]:
        return "🌦️"
    if cloud >= 80 or c == 3:
        return "☁️"
    if cloud >= 35 or c in [1, 2]:
        return "⛅"
    return "☀️"

# Seuils recalibrés, moins nerveux
def code_level(score):
    s = fnum(score)
    if s < 40:
        return "VERT", "#15803d", "Calme"
    if s < 60:
        return "JAUNE", "#ca8a04", "À surveiller"
    if s < 78:
        return "ORANGE", "#f97316", "Significatif"
    if s < 92:
        return "ROUGE", "#dc2626", "Fort"
    return "VIOLET", "#7c3aed", "Sévère"

@st.cache_data(ttl=600)
def load_data():
    r = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={
            "latitude": LAT,
            "longitude": LON,
            "hourly": ",".join(HOURLY),
            "forecast_days": 8,
            "timezone": "Europe/Brussels",
            "wind_speed_unit": "kmh",
        },
        timeout=25,
    )
    r.raise_for_status()

    df = pd.DataFrame(r.json()["hourly"])
    df["time"] = pd.to_datetime(df["time"])

    for col in HOURLY:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["temps"] = df["weather_code"].apply(weather_text)
    df["direction_vent"] = df["wind_direction_10m"].apply(compass)

    return add_scores(df)

def add_scores(df):
    d = df.copy()

    cape = d["cape"].fillna(0)
    precip = d["precipitation"].fillna(0)
    proba = d["precipitation_probability"].fillna(0)
    gust = d["wind_gusts_10m"].fillna(0)
    hum = d["relative_humidity_2m"].fillna(0)
    dew = d["dew_point_2m"].fillna(0)
    temp = d["temperature_2m"].fillna(0)
    freezing = d["freezing_level_height"].replace(0, np.nan).fillna(2500)

    # Formules adoucies pour éviter jaune/orange trop vite
    d["score_orage"] = (
        (cape / 38).clip(0, 38)
        + (precip * 6).clip(0, 22)
        + ((gust - 38) * 0.50).clip(0, 24)
        + ((hum - 65) * 0.18).clip(0, 8)
    ).clip(0, 100).round(1)

    d["score_pluie_intense"] = ((precip * 11) + (proba * 0.30)).clip(0, 100).round(1)

    d["score_grele"] = (
        (cape / 55).clip(0, 38)
        + ((4400 - freezing) / 80).clip(0, 22)
        + ((gust - 30) / 3.5).clip(0, 26)
    ).clip(0, 100).round(1)

    d["risque_downburst"] = (
        ((gust - 60) * 1.00).clip(0, 42)
        + ((temp - 25) * 0.90).clip(0, 18)
        + ((100 - hum) * 0.18).clip(0, 17)
        + (cape / 190).clip(0, 10)
    ).clip(0, 100).round(1)

    d["risque_supercellule"] = (
        (cape / 85).clip(0, 32)
        + ((gust - 55) * 0.65).clip(0, 28)
        + ((dew - 14) * 1.20).clip(0, 18)
        + ((4400 - freezing) / 190).clip(0, 8)
    ).clip(0, 100).round(1)

    d["score_tornade_approximatif"] = (
        (cape / 115).clip(0, 24)
        + ((gust - 58) * 0.55).clip(0, 28)
        + ((dew - 14) * 1.45).clip(0, 16)
    ).clip(0, 100).round(1)

    d["fog"] = d.apply(lambda r: 1 if fog_possible(r) else 0, axis=1)
    return d

def css():
    st.markdown("""
<style>
.block-container {
    max-width: 570px;
    padding-top: 0.8rem;
    padding-left: 0.7rem;
    padding-right: 0.7rem;
}
div[data-testid="stToolbar"] {display:none;}
.hero {
    background: linear-gradient(160deg,#2563eb 0%,#1e3a8a 46%,#020617 100%);
    border-radius: 30px;
    padding: 22px;
    color: white;
    margin-bottom: 14px;
    box-shadow: 0 14px 30px rgba(0,0,0,.30);
}
.card {
    background:#0f172a;
    border:1px solid #263244;
    color:white;
    border-radius:18px;
    padding:12px;
    text-align:center;
    margin-bottom:10px;
}
.soft {
    background:#111827;
    border:1px solid #263244;
    color:white;
    border-radius:18px;
    padding:14px;
    margin-bottom:10px;
}
.period {
    background:#0f172a;
    border:1px solid #263244;
    color:white;
    border-radius:18px;
    padding:12px;
    margin-bottom:10px;
}
.alert {
    color:white;
    border-radius:22px;
    padding:15px 16px;
    margin-bottom:14px;
    font-weight:850;
}
.pill {
    color:white;
    padding:5px 9px;
    border-radius:999px;
    font-weight:850;
    font-size:12px;
    display:inline-block;
}
.bigcode {
    font-size:30px;
    font-weight:950;
    letter-spacing:.02em;
}
.small {
    font-size:12px;
    opacity:.86;
}
a {color:#93c5fd!important;}
</style>
""", unsafe_allow_html=True)

def risk_24h(df):
    n = df.head(24)
    storm = fnum(n["score_orage"].max())
    rain = fnum(n["score_pluie_intense"].max())
    hail = fnum(n["score_grele"].max())
    down = fnum(n["risque_downburst"].max())
    sup = fnum(n["risque_supercellule"].max())
    tor = fnum(n["score_tornade_approximatif"].max())
    gust = fnum(n["wind_gusts_10m"].max())

    # Score global plus prudent
    global_score = max(storm, rain * 0.70, hail, down, sup, tor)
    return global_score, storm, rain, hail, down, sup, tor, gust

def summarize_period(part):
    if part.empty:
        return None

    mid = part.iloc[len(part) // 2]
    temp = fnum(part["temperature_2m"].mean())
    feel = fnum(part["apparent_temperature"].mean())
    rain = fnum(part["precipitation"].sum())
    rain_proba = fnum(part["precipitation_probability"].max())
    gust = fnum(part["wind_gusts_10m"].max())
    wind = fnum(part["wind_speed_10m"].mean())
    storm = fnum(part["score_orage"].max())
    hail = fnum(part["score_grele"].max())
    fog = int(part["fog"].max()) == 1
    uv = fnum(part["uv_index"].max())
    hum = fnum(part["relative_humidity_2m"].mean())

    icon = "🌫️" if fog else icon_for(mid, storm)
    code, color, label = code_level(max(storm, rain_proba * 0.45, hail))

    return {
        "icon": icon,
        "temp": temp,
        "feel": feel,
        "rain": rain,
        "rain_proba": rain_proba,
        "gust": gust,
        "wind": wind,
        "storm": storm,
        "hail": hail,
        "fog": fog,
        "uv": uv,
        "hum": hum,
        "code": code,
        "color": color,
        "label": label,
    }

def render_home(df):
    r = df.iloc[0]
    storm = fnum(r["score_orage"])
    ico = icon_for(r, storm)
    desc = "Brume / brouillard possible" if fog_possible(r) else r["temps"]

    st.markdown(f"""
<div class="hero">
  <div style="font-size:34px;font-weight:950;">Frasnes / Rèves</div>
  <div style="opacity:.82;margin-bottom:15px;">Mobile météo • {pd.to_datetime(r["time"]).strftime("%d/%m %H:%M")}</div>
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <div>
      <div style="font-size:68px;font-weight:950;line-height:.92;">{fnum(r["temperature_2m"]):.1f}°C</div>
      <div style="font-size:21px;">Ressenti {fnum(r["apparent_temperature"]):.1f}°C</div>
      <div style="font-size:17px;margin-top:10px;">{desc}</div>
    </div>
    <div style="font-size:78px;">{ico}</div>
  </div>
</div>
""", unsafe_allow_html=True)

    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown(f'<div class="card"><b>Pluie</b><br><span style="font-size:22px;font-weight:900;">{fnum(r["precipitation"]):.1f} mm</span></div>', unsafe_allow_html=True)
    with c2:
        st.markdown(f'<div class="card"><b>Vent</b><br><span style="font-size:22px;font-weight:900;">{fnum(r["wind_speed_10m"]):.0f} km/h</span></div>', unsafe_allow_html=True)
    with c3:
        st.markdown(f'<div class="card"><b>Rafales</b><br><span style="font-size:22px;font-weight:900;">{fnum(r["wind_gusts_10m"]):.0f} km/h</span></div>', unsafe_allow_html=True)

    global_score, storm, rain, hail, down, sup, tor, gust = risk_24h(df)
    code, color, label = code_level(global_score)

    st.markdown(f"""
<div class="alert" style="background:{color};">
  <div class="bigcode">CODE {code}</div>
  {label} sur 24h<br>
  <span class="small">⛈️ {storm:.0f}/100 · 🌧️ {rain:.0f}/100 · 🧊 {hail:.0f}/100 · 🌀 {sup:.0f}/100 · 💨 {gust:.0f} km/h</span>
</div>
""", unsafe_allow_html=True)

def render_today_periods(df):
    st.markdown("### Aujourd’hui")
    today = pd.Timestamp.now(tz="Europe/Brussels").tz_localize(None).date()
    d = df[pd.to_datetime(df["time"]).dt.date == today].copy()

    for name, h1, h2 in PERIODES:
        part = d[(pd.to_datetime(d["time"]).dt.hour >= h1) & (pd.to_datetime(d["time"]).dt.hour < h2)]
        s = summarize_period(part)

        if not s:
            st.markdown(f'<div class="period"><b>{name}</b><br>—</div>', unsafe_allow_html=True)
            continue

        fog = " · 🌫️ brume/brouillard possible" if s["fog"] else ""

        st.markdown(f"""
<div class="period">
  <div style="display:flex;align-items:center;justify-content:space-between;">
    <div><b>{name}</b><br><span class="small">{s["label"]}{fog}</span></div>
    <div style="font-size:35px;">{s["icon"]}</div>
    <span class="pill" style="background:{s["color"]};">{s["code"]}</span>
  </div>
  <div style="margin-top:8px;font-size:14px;">
    🌡️ {s["temp"]:.0f}°C · ressenti {s["feel"]:.0f}°C<br>
    💧 {s["rain"]:.1f} mm · proba {s["rain_proba"]:.0f}%<br>
    💨 vent {s["wind"]:.0f} km/h · rafales {s["gust"]:.0f} km/h<br>
    ⛈️ orage {s["storm"]:.0f}/100 · 🧊 grêle {s["hail"]:.0f}/100 · UV {s["uv"]:.1f}
  </div>
</div>
""", unsafe_allow_html=True)

def render_week_periods(df):
    st.markdown("### Semaine matin / après-midi / soirée / nuit")
    d = df.copy()
    d["date"] = pd.to_datetime(d["time"]).dt.date
    dates = list(d["date"].drop_duplicates())[:7]

    for date in dates:
        day = d[d["date"] == date]
        st.markdown(f"#### {pd.to_datetime(date).strftime('%A %d/%m')}")

        for name, h1, h2 in PERIODES:
            part = day[(pd.to_datetime(day["time"]).dt.hour >= h1) & (pd.to_datetime(day["time"]).dt.hour < h2)]
            s = summarize_period(part)

            if not s:
                continue

            fog = " 🌫️" if s["fog"] else ""

            st.markdown(f"""
<div class="soft">
  <div style="display:flex;align-items:center;justify-content:space-between;">
    <div><b>{name}</b>{fog}<br><span class="small">{s["label"]}</span></div>
    <div style="font-size:30px;">{s["icon"]}</div>
    <span class="pill" style="background:{s["color"]};">{s["code"]}</span>
  </div>
  <div style="margin-top:8px;font-size:13px;">
    🌡️ {s["temp"]:.0f}°C · 💧 {s["rain"]:.1f} mm / {s["rain_proba"]:.0f}% · 💨 {s["gust"]:.0f} km/h · ⛈️ {s["storm"]:.0f}/100
  </div>
</div>
""", unsafe_allow_html=True)

def render_alerts(df):
    st.markdown("### Alertes détaillées")
    global_score, storm, rain, hail, down, sup, tor, gust = risk_24h(df)
    code, color, label = code_level(global_score)

    st.markdown(f'<div class="alert" style="background:{color};"><div class="bigcode">CODE {code}</div>{label}</div>', unsafe_allow_html=True)

    for name, value in [
        ("⛈️ Orage", storm),
        ("🌧️ Pluie intense", rain),
        ("🧊 Grêle", hail),
        ("⬇️ Rafales descendantes", down),
        ("🌀 Supercellule", sup),
        ("🌪️ Tornade approximative", tor),
    ]:
        c, col, lab = code_level(value)
        st.markdown(f'<div class="soft"><b>{name}</b><br><span style="font-size:24px;font-weight:950;">{value:.0f}/100</span><br><span class="pill" style="background:{col};">CODE {c}</span> {lab}</div>', unsafe_allow_html=True)

    fog = "possible" if int(df.head(24)["fog"].sum()) else "non détecté"
    st.markdown(f'<div class="soft"><b>🌫️ Brume / brouillard 24h</b><br><span style="font-size:23px;font-weight:900;">{fog}</span></div>', unsafe_allow_html=True)

def render_radar():
    st.markdown("### Radar & liens utiles")
    st.link_button("📡 Radar Windy", "https://www.windy.com/50.538/4.452")
    st.link_button("🌧️ Radar RainViewer", "https://www.rainviewer.com/map.html?loc=50.5384,4.4523,8")
    st.link_button("🇧🇪 IRM Belgique", "https://www.meteo.be")
    st.link_button("🌩️ Kachelmann", "https://kachelmannwetter.com/be")

def render_details(df):
    st.markdown("### Détails actuels")
    r = df.iloc[0]
    c1, c2 = st.columns(2)
    with c1:
        st.metric("Humidité", f"{fnum(r['relative_humidity_2m']):.0f}%")
        st.metric("Point de rosée", f"{fnum(r['dew_point_2m']):.1f}°C")
        st.metric("Pression", f"{fnum(r['pressure_msl']):.1f} hPa")
        st.metric("UV", f"{fnum(r['uv_index']):.1f}")
    with c2:
        st.metric("Vent", f"{fnum(r['wind_speed_10m']):.0f} km/h")
        st.metric("Rafales", f"{fnum(r['wind_gusts_10m']):.0f} km/h")
        st.metric("Direction", r["direction_vent"])
        st.metric("CAPE", f"{fnum(r['cape']):.0f}")

css()

try:
    df = load_data()
    now = pd.Timestamp.now(tz="Europe/Brussels").tz_localize(None)
    df = df[df["time"] >= now].copy()

    tab_home, tab_week, tab_alerts, tab_radar, tab_details = st.tabs([
        "🏠 Jour",
        "📅 Semaine",
        "⚠️ Alertes",
        "🌧️ Radar",
        "📊 Détails",
    ])

    with tab_home:
        render_home(df)
        render_today_periods(df)
        st.caption("V12 mobile — météo du jour matin/après-midi/soirée/nuit, seuils alertes adoucis.")

    with tab_week:
        render_week_periods(df)

    with tab_alerts:
        render_alerts(df)

    with tab_radar:
        render_radar()

    with tab_details:
        render_details(df)

except Exception as e:
    st.error("Erreur de chargement météo")
    st.code(str(e))
