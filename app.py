import streamlit as st
import pandas as pd
import numpy as np
import requests
import streamlit.components.v1 as components
from streamlit_autorefresh import st_autorefresh

st.set_page_config(page_title="Station Météo — Frasnes / Rèves", page_icon="⛈️", layout="wide")

# Auto-refresh toutes les 10 minutes
st_autorefresh(interval=600000, key="meteo_refresh")

st.title("⛈️ Station Météo — Frasnes / Rèves")

LAT_DEFAULT = 50.5384
LON_DEFAULT = 4.4523
REVES_URL = "https://reves.meteo-be.net/"

HOURLY = [
    "temperature_2m","apparent_temperature","precipitation","precipitation_probability",
    "weather_code","cloud_cover","cloud_cover_low","cloud_cover_mid","cloud_cover_high",
    "wind_speed_10m","wind_gusts_10m","wind_direction_10m","relative_humidity_2m",
    "dew_point_2m","pressure_msl","visibility","uv_index","cape","freezing_level_height"
]

MODELS = {
    "Best match Open-Meteo": "best_match",

    # Haute résolution Belgique / nord France
    "AROME France HD": "meteofrance_arome_france_hd",
    "AROME France": "meteofrance_arome_france",
    "ICON-D2": "icon_d2",
    "ICON-EU": "icon_eu",
    "ICON Global": "icon_global",
    "HARMONIE KNMI": "knmi_harmonie_arome_europe",
    "HARMONIE DMI": "dmi_harmonie_arome_europe",

    # Globaux / longue échéance
    "GFS Global": "gfs_global",
    "ECMWF IFS 0.4°": "ecmwf_ifs04",
}

METAR_STATIONS = {
    "Charleroi / Brussels South — EBCI": "EBCI",
    "Bruxelles / Zaventem — EBBR": "EBBR",
    "Liège — EBLG": "EBLG",
    "Florennes — EBFS": "EBFS",
    "Beauvechain — EBBE": "EBBE",
    "Chièvres — EBCV": "EBCV",
}

def clean_numeric(df):
    df = df.copy()
    for col in df.columns:
        if col == "time" or col == "modele" or col in ["temps","type_nuages"]:
            continue
        df[col] = pd.to_numeric(df[col], errors="ignore")
    return df

def display_table(df, decimals=1):
    """Formate uniquement une copie pour l'affichage. Ne modifie jamais les calculs."""
    out = df.copy()
    for col in out.columns:
        if pd.api.types.is_numeric_dtype(out[col]):
            if col == "pressure_msl" or col == "pression_hPa_moyenne":
                out[col] = out[col].apply(lambda x: "" if pd.isna(x) else f"{float(x):.{decimals}f} hPa")
            else:
                out[col] = out[col].apply(lambda x: "" if pd.isna(x) else f"{float(x):.{decimals}f}")
    return out.rename(columns={"pressure_msl": "pression_hPa"})

def deg_to_compass(deg):
    """Convertit une direction en degrés vers N, NE, E, SE, S, SO, O, NO."""
    try:
        if pd.isna(deg):
            return ""
        deg = float(deg) % 360
    except Exception:
        return ""
    dirs = ["N", "NE", "E", "SE", "S", "SO", "O", "NO"]
    ix = int((deg + 22.5) // 45) % 8
    return dirs[ix]


def weather_text(code):
    try:
        code = int(code)
    except Exception:
        return "indéterminé"
    mapping = {
        0:"ciel clair",1:"peu nuageux",2:"partiellement nuageux",3:"couvert",
        45:"brouillard",48:"brouillard givrant",51:"bruine faible",53:"bruine",55:"bruine forte",
        61:"pluie faible",63:"pluie",65:"pluie forte",71:"neige faible",73:"neige",75:"neige forte",
        80:"averses faibles",81:"averses",82:"averses fortes",95:"orage",96:"orage avec grêle",99:"orage violent avec grêle"
    }
    return mapping.get(code, "variable")

def dominant_cloud(row):
    vals = {}
    for label, col in [("bas","cloud_cover_low"),("moyens","cloud_cover_mid"),("hauts","cloud_cover_high")]:
        v = row.get(col, 0)
        if pd.isna(v):
            v = 0
        vals[label] = float(v)
    if max(vals.values()) < 20:
        return "peu de nuages"
    return "nuages " + max(vals, key=vals.get) + " dominants"

def compute_scores(df):
    d = df.copy()

    for col in HOURLY:
        if col not in d.columns:
            d[col] = np.nan

    for col in [c for c in HOURLY if c != "weather_code"]:
        d[col] = pd.to_numeric(d[col], errors="coerce")

    # Ne jamais remplacer la pression manquante par 0,
    # sinon la moyenne multi-modèles devient artificiellement trop basse.
    if "pressure_msl" in d.columns:
        d["pressure_msl"] = pd.to_numeric(d["pressure_msl"], errors="coerce")

    # Sauvegarder les valeurs manquantes avant remplissage.
    # Important : elles ne doivent PAS compter comme 0 dans la moyenne multi-modèles.
    base_weather_cols = [
        "temperature_2m","apparent_temperature","precipitation","precipitation_probability",
        "cloud_cover","cloud_cover_low","cloud_cover_mid","cloud_cover_high",
        "wind_speed_10m","wind_gusts_10m","wind_direction_10m","relative_humidity_2m",
        "dew_point_2m","visibility","uv_index","cape","freezing_level_height"
    ]
    missing_masks = {col: d[col].isna() for col in base_weather_cols if col in d.columns}

    # Pour les calculs de scores uniquement, on utilise des copies remplies.
    for col in base_weather_cols:
        if col in d.columns:
            d[col] = d[col].fillna(0)

    d["temps"] = d["weather_code"].apply(weather_text)
    d["type_nuages"] = d.apply(dominant_cloud, axis=1)
    d["ensoleillement_score"] = (100 - d["cloud_cover"]).clip(0,100)

    d["score_orage"] = (
        (d["cape"]/30).clip(0,45)
        + (d["precipitation"]*8).clip(0,30)
        + ((d["wind_gusts_10m"]-30)*0.7).clip(0,25)
        + ((d["relative_humidity_2m"]-55)*0.25).clip(0,10)
    ).clip(0,100).round(1)

    d["score_pluie_intense"] = ((d["precipitation"]*15) + (d["precipitation_probability"]*0.4)).clip(0,100).round(1)

    freezing = d["freezing_level_height"].replace(0, np.nan).fillna(2500)
    d["score_grele"] = (
        (d["cape"]/45).clip(0,45)
        + ((4500-freezing)/60).clip(0,25)
        + (d["wind_gusts_10m"]/3).clip(0,30)
    ).clip(0,100).round(1)

    d["grele_estimee_cm"] = np.where(d["score_grele"] < 35, 0, ((d["score_grele"]-30)/18).clip(0,6)).round(1)

    d["score_tornade_approximatif"] = (
        (d["cape"]/80).clip(0,30)
        + ((d["wind_gusts_10m"]-45)*0.8).clip(0,35)
        + ((d["dew_point_2m"]-12)*2).clip(0,20)
    ).clip(0,100).round(1)

    d["risque_downburst"] = (
        ((d["wind_gusts_10m"]-50)*1.2).clip(0,45)
        + ((d["temperature_2m"]-20)*1.2).clip(0,25)
        + ((100-d["relative_humidity_2m"])*0.25).clip(0,20)
        + (d["cape"]/120).clip(0,10)
    ).clip(0,100).round(1)

    d["risque_supercellule"] = (
        (d["cape"]/60).clip(0,35)
        + ((d["wind_gusts_10m"]-45)*0.8).clip(0,35)
        + ((d["dew_point_2m"]-12)*1.5).clip(0,20)
        + ((4500-freezing)/150).clip(0,10)
    ).clip(0,100).round(1)

    d["direction_vent"] = d["wind_direction_10m"].apply(deg_to_compass)

    # Restaurer les valeurs météo manquantes en NaN pour que la moyenne ignore ces modèles.
    for col, mask in missing_masks.items():
        if col in d.columns:
            d.loc[mask, col] = np.nan

    # Restaurer les valeurs météo manquantes avant moyenne multi-modèles.
    if "missing_masks" in locals():
        for col, mask in missing_masks.items():
            if col in d.columns:
                d.loc[mask, col] = np.nan

    return d.loc[:, ~d.columns.duplicated()].copy()

def fetch_model(lat, lon, days, name, code):
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": ",".join(HOURLY),
        "forecast_days": min(days + 1, 16),
        "timezone": "Europe/Brussels",
        "wind_speed_unit": "kmh"
    }
    if code != "best_match":
        params["models"] = code

    r = requests.get("https://api.open-meteo.com/v1/forecast", params=params, timeout=25)
    r.raise_for_status()
    data = r.json()

    if "hourly" not in data:
        return pd.DataFrame()

    df = pd.DataFrame(data["hourly"])
    if "time" not in df.columns:
        return pd.DataFrame()

    df["time"] = pd.to_datetime(df["time"])
    df["modele"] = name
    return compute_scores(df)

@st.cache_data(ttl=900)
def load_forecast(lat, lon, days, selected):
    frames = []
    errors = []

    for name in selected:
        try:
            f = fetch_model(lat, lon, days, name, MODELS[name])
            if not f.empty:
                frames.append(f)
        except Exception as e:
            errors.append(f"{name}: {str(e)[:180]}")

    if not frames:
        return pd.DataFrame(), pd.DataFrame(), errors

    all_df = pd.concat(frames, ignore_index=True)
    all_df = all_df.loc[:, ~all_df.columns.duplicated()].copy()

    numeric_cols = all_df.select_dtypes(include=[np.number]).columns.tolist()
    avg = all_df.groupby("time", as_index=False)[numeric_cols].mean()

    text = all_df.drop_duplicates("time")[["time","temps","type_nuages"]]
    avg = avg.merge(text, on="time", how="left")
    if "wind_direction_10m" in avg.columns:
        avg["direction_vent"] = avg["wind_direction_10m"].apply(deg_to_compass)
    avg["modele"] = "Moyenne multi-modèles"

    for c in avg.select_dtypes(include=[np.number]).columns:
        avg[c] = avg[c].round(1)
    for c in all_df.select_dtypes(include=[np.number]).columns:
        all_df[c] = all_df[c].round(1)

    return avg.loc[:, ~avg.columns.duplicated()].copy(), all_df, errors

@st.cache_data(ttl=300)
def fetch_metar(station):
    url = "https://aviationweather.gov/api/data/metar"
    params = {"ids": station, "format": "json", "hours": 2}
    try:
        r = requests.get(url, params=params, timeout=10)
        if r.status_code == 204:
            return None, "Pas de METAR disponible pour le moment."
        r.raise_for_status()
        data = r.json()
        if not data:
            return None, "Pas de METAR disponible pour le moment."
        return data[0], None
    except requests.exceptions.Timeout:
        return None, "Le serveur METAR aviationweather.gov ne répond pas assez vite. Réessaie plus tard ou clique sur Actualiser."
    except requests.exceptions.RequestException as e:
        return None, f"METAR temporairement indisponible : {e}"
    except Exception as e:
        return None, f"Erreur METAR : {e}"

def kts_to_kmh(x):
    try:
        return round(float(x) * 1.852, 1)
    except Exception:
        return None

def metar_card(metar):
    if not metar:
        return
    cols = st.columns(5)
    cols[0].metric("Station", metar.get("icaoId","?"))
    cols[1].metric("Temp.", f"{metar.get('temp','?')} °C")
    cols[2].metric("Point rosée", f"{metar.get('dewp','?')} °C")
    cols[3].metric("Vent", f"{kts_to_kmh(metar.get('wspd')) or '?'} km/h")
    cols[4].metric("Visibilité", f"{metar.get('visib','?')} SM")
    st.code(metar.get("rawOb","METAR non disponible"))

def daily_summary(df):
    d = df.copy()

    # sécurité : s'assurer que les colonnes restent numériques
    numeric_needed = [
        "temperature_2m","apparent_temperature","precipitation","precipitation_probability",
        "cloud_cover","ensoleillement_score","wind_speed_10m","wind_gusts_10m",
        "relative_humidity_2m","pressure_msl","score_orage","score_grele",
        "score_tornade_approximatif","risque_downburst","risque_supercellule"
    ]

    for c in numeric_needed:
        if c not in d.columns:
            d[c] = np.nan if c == "pressure_msl" else 0
        d[c] = pd.to_numeric(d[c], errors="coerce")
        if c != "pressure_msl":
            d[c] = d[c].fillna(0)

    d["date"] = pd.to_datetime(d["time"]).dt.date

    ag = d.groupby("date").agg(
        temp_min=("temperature_2m","min"),
        temp_max=("temperature_2m","max"),
        ressenti_min=("apparent_temperature","min"),
        ressenti_max=("apparent_temperature","max"),
        pluie_totale_mm=("precipitation","sum"),
        proba_pluie_max=("precipitation_probability","max"),
        nuages_moyens_pct=("cloud_cover","mean"),
        soleil_score_moyen=("ensoleillement_score","mean"),
        vent_max=("wind_speed_10m","max"),
        direction_vent_moyenne=("wind_direction_10m","mean"),
        rafales_max=("wind_gusts_10m","max"),
        humidite_moyenne=("relative_humidity_2m","mean"),
        pression_hPa_moyenne=("pressure_msl","mean"),
        score_orage_max=("score_orage","max"),
        score_grele_max=("score_grele","max"),
        score_tornade_max=("score_tornade_approximatif","max"),
        downburst_max=("risque_downburst","max"),
        supercellule_max=("risque_supercellule","max")
    ).reset_index()

    if "direction_vent_moyenne" in ag.columns:
        ag["direction_vent"] = ag["direction_vent_moyenne"].apply(deg_to_compass)
        # Placer direction_vent juste après vent_max
        cols = list(ag.columns)
        if "direction_vent" in cols and "rafales_max" in cols:
            cols.remove("direction_vent")
            cols.insert(cols.index("rafales_max") + 1, "direction_vent")
            ag = ag[cols]
        ag = ag.drop(columns=["direction_vent_moyenne"], errors="ignore")

    for c in ag.select_dtypes(include=[np.number]).columns:
        ag[c] = ag[c].round(1)

    return ag

def alert_level(row):
    alerts = []
    if row.get("score_orage",0) >= 70:
        alerts.append(("⛈️ Orage fort", "Score orage élevé"))
    if row.get("score_grele",0) >= 60:
        alerts.append(("🧊 Grêle", f"Grêle estimée jusqu’à {row.get('grele_estimee_cm',0):.1f} cm"))
    if row.get("score_pluie_intense",0) >= 70:
        alerts.append(("🌧️ Pluie intense", "Risque de fortes intensités"))
    if row.get("wind_gusts_10m",0) >= 70:
        alerts.append(("💨 Rafales fortes", f"{row.get('wind_gusts_10m',0):.0f} km/h"))
    if row.get("score_tornade_approximatif",0) >= 55:
        alerts.append(("🌪️ Rotation possible", "Indice tornade indicatif élevé"))
    if row.get("risque_downburst",0) >= 65:
        alerts.append(("⬇️ Downburst", "Risque de rafales descendantes"))
    if row.get("risque_supercellule",0) >= 65:
        alerts.append(("🌀 Supercellule", "Configuration à surveiller"))
    return alerts

def color_score(val):
    try:
        v = float(str(val).replace(",", ".").split("/")[0])
    except Exception:
        return ""

    if v < 20:
        return "background-color: #1e7f3f; color: white"
    elif v < 40:
        return "background-color: #c9a227; color: black"
    elif v < 60:
        return "background-color: #d97a1d; color: white"
    elif v < 80:
        return "background-color: #c0392b; color: white"
    else:
        return "background-color: #6c3483; color: white"

def format_score_columns(df, score_cols):
    out = df.copy()
    for c in score_cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").fillna(0).apply(lambda x: f"{x:.1f}/100")
    return out

def radar_html(lat, lon):
    return f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8"/>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  #map {{ height: 620px; width: 100%; border-radius: 14px; }}
  .info {{ position:absolute; z-index:1000; background:white; padding:8px; border-radius:8px; top:10px; left:10px; font-family:Arial; font-size:13px; }}
</style>
</head>
<body>
<div id="map"></div>
<div class="info">Radar pluie RainViewer — animation live</div>
<script>
var map = L.map('map', {{minZoom:5, maxZoom:10}}).setView([{lat}, {lon}], 7);
L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap'
}}).addTo(map);
L.marker([{lat}, {lon}]).addTo(map).bindPopup("Frasnes / Rèves").openPopup();

fetch('https://api.rainviewer.com/public/weather-maps.json')
.then(r => r.json())
.then(apiData => {{
    var frames = apiData.radar.past;
    var host = apiData.host;
    var i = frames.length - 1;
    var radar = L.tileLayer(host + frames[i].path + '/256/{{z}}/{{x}}/{{y}}/2/1_1.png', {{
        tileSize: 256, opacity: 0.65, zIndex: 10, attribution: 'RainViewer', minZoom: 5, maxZoom: 10
    }}).addTo(map);
    setInterval(function() {{
        i = (i + 1) % frames.length;
        map.removeLayer(radar);
        radar = L.tileLayer(host + frames[i].path + '/256/{{z}}/{{x}}/{{y}}/2/1_1.png', {{
            tileSize: 256, opacity: 0.65, zIndex: 10, attribution: 'RainViewer', minZoom: 5, maxZoom: 10
        }}).addTo(map);
    }}, 1200);
}})
.catch(err => console.log(err));
</script>
</body>
</html>
"""


def visual_weather_icon(code, precip=0, cloud=0, score_orage=0):
    try:
        code = int(code)
        precip = float(precip)
        cloud = float(cloud)
        score_orage = float(score_orage)
    except Exception:
        code, precip, cloud, score_orage = 3, 0, 80, 0
    if score_orage >= 70 or code in [95, 96, 99]:
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

def app_risk_color(score):
    try:
        score = float(score)
    except Exception:
        score = 0
    if score < 20:
        return "#1e7f3f"
    if score < 40:
        return "#d4b106"
    if score < 60:
        return "#d97706"
    if score < 80:
        return "#dc2626"
    return "#7c3aed"

def app_risk_label(score):
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

def render_interface_app(avg_table, days=3):
    if avg_table.empty:
        st.warning("Aucune donnée disponible pour l'interface app.")
        return

    now_row = avg_table.iloc[0]
    icon = visual_weather_icon(now_row.get("weather_code", 3), now_row.get("precipitation", 0), now_row.get("cloud_cover", 0), now_row.get("score_orage", 0))
    risk = float(now_row.get("score_orage", 0) or 0)
    risk_color = app_risk_color(risk)
    risk_label = app_risk_label(risk)

    st.markdown("""
    <style>
    .app-card {background: linear-gradient(135deg,#174ea6 0%,#1d4ed8 45%,#0f172a 100%);border-radius:28px;padding:26px;color:white;box-shadow:0 14px 35px rgba(0,0,0,.35);margin-bottom:18px;}
    .app-title {font-size:34px;font-weight:800;margin-bottom:6px;}
    .app-sub {opacity:.85;font-size:15px;}
    .app-temp {font-size:76px;line-height:.95;font-weight:800;}
    .app-icon {font-size:86px;text-align:center;}
    .mini-card {background:rgba(255,255,255,.12);border:1px solid rgba(255,255,255,.20);border-radius:18px;padding:14px;text-align:center;color:white;}
    .hour-strip {display:flex;gap:10px;overflow-x:auto;padding-bottom:8px;}
    .hour-card {min-width:92px;background:#111827;border:1px solid #263244;border-radius:18px;padding:12px 10px;text-align:center;color:white;}
    .hour-icon {font-size:30px;}
    .day-row {display:grid;grid-template-columns:90px 52px 110px 90px 90px 90px 1fr;gap:8px;align-items:center;background:#111827;border:1px solid #263244;border-radius:16px;padding:10px 12px;color:white;margin-bottom:8px;}
    .risk-pill {display:inline-block;padding:5px 10px;border-radius:999px;font-weight:700;color:white;font-size:13px;}
    </style>
    """, unsafe_allow_html=True)

    st.markdown(f"""
    <div class="app-card">
        <div class="app-title">Frasnes / Rèves</div>
        <div class="app-sub">Prévision multi-modèles • {pd.to_datetime(now_row["time"]).strftime("%d/%m/%Y %H:%M")}</div>
        <div style="display:grid;grid-template-columns:1.3fr .7fr;gap:20px;align-items:center;margin-top:18px;">
            <div>
                <div class="app-temp">{float(now_row.get("temperature_2m",0)):.1f}°C</div>
                <div style="font-size:20px;margin-top:6px;">Ressenti {float(now_row.get("apparent_temperature",0)):.1f}°C</div>
                <div style="font-size:17px;opacity:.9;margin-top:6px;">{now_row.get("temps","variable")}</div>
            </div>
            <div class="app-icon">{icon}</div>
        </div>
        <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin-top:22px;">
            <div class="mini-card"><b>Pluie</b><br>{float(now_row.get("precipitation",0)):.1f} mm</div>
            <div class="mini-card"><b>Vent</b><br>{float(now_row.get("wind_speed_10m",0)):.0f} km/h</div>
            <div class="mini-card"><b>Rafales</b><br>{float(now_row.get("wind_gusts_10m",0)):.0f} km/h</div>
            <div class="mini-card"><b>Humidité</b><br>{float(now_row.get("relative_humidity_2m",0)):.0f} %</div>
            <div class="mini-card"><b>Orage</b><br><span style="background:{risk_color};padding:4px 9px;border-radius:99px;">{risk:.0f}/100</span></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    max_storm = float(avg_table.head(24).get("score_orage", pd.Series([0])).max())
    max_gust = float(avg_table.head(24).get("wind_gusts_10m", pd.Series([0])).max())
    max_rain = float(avg_table.head(24).get("score_pluie_intense", pd.Series([0])).max())
    max_super = float(avg_table.head(24).get("risque_supercellule", pd.Series([0])).max())
    max_risk = max(max_storm, max_rain, max_super)
    banner_color = app_risk_color(max_risk)
    banner_label = app_risk_label(max_risk)
    st.markdown(f"""
    <div style="background:{banner_color};color:white;border-radius:18px;padding:14px 18px;margin-bottom:18px;font-weight:700;">
        ⚠️ Niveau vigilance 24h : {banner_label} — Orage {max_storm:.0f}/100 • Pluie intense {max_rain:.0f}/100 • Supercellule {max_super:.0f}/100 • Rafales max {max_gust:.0f} km/h
    </div>
    """, unsafe_allow_html=True)

    st.subheader("⏰ Prochaines heures")
    hour_html = '<div class="hour-strip">'
    for _, r in avg_table.head(12).iterrows():
        h_icon = visual_weather_icon(r.get("weather_code",3), r.get("precipitation",0), r.get("cloud_cover",0), r.get("score_orage",0))
        h_risk_color = app_risk_color(r.get("score_orage",0))
        hour_html += f"""
        <div class="hour-card">
            <div style="opacity:.8;">{pd.to_datetime(r["time"]).strftime("%H:%M")}</div>
            <div class="hour-icon">{h_icon}</div>
            <div style="font-size:22px;font-weight:800;">{float(r.get("temperature_2m",0)):.0f}°</div>
            <div style="font-size:12px;">💧 {float(r.get("precipitation",0)):.1f} mm</div>
            <div style="font-size:12px;">💨 {float(r.get("wind_gusts_10m",0)):.0f}</div>
            <div style="height:5px;background:{h_risk_color};border-radius:99px;margin-top:8px;"></div>
        </div>
        """
    hour_html += "</div>"
    st.markdown(hour_html, unsafe_allow_html=True)

    st.subheader("📅 Prochains jours")
    d = avg_table.copy()
    d["date"] = pd.to_datetime(d["time"]).dt.date
    daily = d.groupby("date").agg(
        temp_min=("temperature_2m","min"),
        temp_max=("temperature_2m","max"),
        rain=("precipitation","sum"),
        gust=("wind_gusts_10m","max"),
        storm=("score_orage","max"),
        supercell=("risque_supercellule","max"),
        code=("weather_code","first"),
        cloud=("cloud_cover","mean")
    ).reset_index().head(days)

    for _, r in daily.iterrows():
        d_icon = visual_weather_icon(r.get("code",3), r.get("rain",0), r.get("cloud",0), r.get("storm",0))
        c = app_risk_color(r.get("storm",0))
        label = app_risk_label(r.get("storm",0))
        st.markdown(f"""
        <div class="day-row">
            <div><b>{pd.to_datetime(r["date"]).strftime("%a")}</b><br>{pd.to_datetime(r["date"]).strftime("%d/%m")}</div>
            <div style="font-size:32px;">{d_icon}</div>
            <div><b>{float(r["temp_min"]):.0f}° / {float(r["temp_max"]):.0f}°C</b></div>
            <div>💧 {float(r["rain"]):.1f} mm</div>
            <div>💨 {float(r["gust"]):.0f} km/h</div>
            <div>⛈️ {float(r["storm"]):.0f}/100</div>
            <div><span class="risk-pill" style="background:{c};">{label}</span></div>
        </div>
        """, unsafe_allow_html=True)

    st.caption("Interface visuelle basée sur la moyenne multi-modèles. Les alertes restent indicatives et doivent être confirmées avec radar/observations.")

# SIDEBAR
st.sidebar.header("Réglages")

if st.sidebar.button("🔄 Actualiser maintenant"):
    st.cache_data.clear()
    st.rerun()

lat = st.sidebar.number_input("Latitude", value=LAT_DEFAULT, format="%.4f")
lon = st.sidebar.number_input("Longitude", value=LON_DEFAULT, format="%.4f")
days = st.sidebar.slider("Nombre de jours", 1, 7, 3)
selected = st.sidebar.multiselect(
    "Modèles",
    list(MODELS.keys()),
    default=[
        "Best match Open-Meteo",
        "AROME France HD",
        "AROME France",
        "ICON-D2",
        "ICON-EU",
        "HARMONIE KNMI",
        "GFS Global",
        "ECMWF IFS 0.4°"
    ]
)
station = st.sidebar.selectbox("METAR officiel proche", list(METAR_STATIONS.keys()), index=0)
st.sidebar.caption("Auto-refresh : 10 minutes. Les tableaux commencent à l’heure actuelle.")

if not selected:
    st.warning("Choisis au moins un modèle.")
    st.stop()

avg, all_models, errors = load_forecast(lat, lon, days, tuple(selected))

if avg.empty:
    st.error("Aucune donnée prévision reçue.")
    st.write(errors)
    st.stop()

now_bxl = pd.Timestamp.now(tz="Europe/Brussels").tz_localize(None)
future = avg[avg["time"] >= now_bxl]
n = future.iloc[0] if not future.empty else avg.iloc[-1]

avg_table = avg[avg["time"] >= now_bxl].copy()
if avg_table.empty:
    avg_table = avg.copy()

all_models_table = all_models[all_models["time"] >= now_bxl].copy()
if all_models_table.empty:
    all_models_table = all_models.copy()

st.caption(f"Valeurs principales prévues pour : {pd.to_datetime(n['time']).strftime('%d/%m/%Y %H:%M')}")

st.caption(f"Modèles utilisés dans la moyenne : {all_models['modele'].nunique()} / {len(selected)}")

if errors:
    with st.expander("Modèles indisponibles ou erreurs API"):
        st.write("Certains modèles peuvent être indisponibles selon l'échéance, la zone ou la variable demandée. Ils sont ignorés dans la moyenne.")
        for e in errors:
            st.write(e)

c1,c2,c3,c4,c5,c6 = st.columns(6)
c1.metric("Température prévue", f"{n.get('temperature_2m',0):.1f} °C")
c2.metric("Ressenti prévu", f"{n.get('apparent_temperature',0):.1f} °C")
c3.metric("Pluie prévue", f"{n.get('precipitation',0):.1f} mm")
c4.metric("Vent prévu", f"{n.get('wind_speed_10m',0):.0f} km/h")
c5.metric("Rafales prévues", f"{n.get('wind_gusts_10m',0):.0f} km/h")
c6.metric("Score orage", f"{n.get('score_orage',0):.0f}/100")

alerts = alert_level(n)
if alerts:
    st.warning(" | ".join([f"{a[0]} — {a[1]}" for a in alerts]))
else:
    st.success("Pas d’alerte forte selon les seuils actuels.")

tab0, tab_app, tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "📡 Observé Rèves","📱 Interface App","🌤️ Météo complète","⛈️ Orages","🌧️ Radar","🛩️ METAR","📅 Résumé","📈 Graphiques","🧪 Par modèle"
])

with tab0:
    components.iframe(REVES_URL, height=850, scrolling=True)

with tab_app:
    render_interface_app(avg_table, days)

with tab1:
    cols = ["time","temps","type_nuages","temperature_2m","apparent_temperature","precipitation","precipitation_probability","cloud_cover","cloud_cover_low","cloud_cover_mid","cloud_cover_high","ensoleillement_score","wind_speed_10m","wind_gusts_10m","direction_vent","wind_direction_10m","relative_humidity_2m","dew_point_2m","pressure_msl","visibility","uv_index"]
    st.dataframe(display_table(avg_table[[c for c in cols if c in avg_table.columns]], 1), use_container_width=True, hide_index=True)
    st.download_button("Télécharger CSV", avg_table.to_csv(index=False).encode("utf-8"), "meteo_orages_frasnes_reves.csv", "text/csv")

with tab2:
    cols = ["time","score_orage","score_pluie_intense","score_grele","grele_estimee_cm","score_tornade_approximatif","risque_downburst","risque_supercellule","cape","freezing_level_height","wind_gusts_10m","dew_point_2m","precipitation"]
    score_cols = ["score_orage","score_pluie_intense","score_grele","score_tornade_approximatif","risque_downburst","risque_supercellule"]

    display_df = avg_table[[c for c in cols if c in avg_table.columns]].copy()
    display_df = format_score_columns(display_df, score_cols)
    display_df = display_table(display_df, 1)

    styled = display_df.style
    for c in score_cols:
        if c in display_df.columns:
            styled = styled.map(color_score, subset=[c])

    st.dataframe(styled, use_container_width=True, hide_index=True)
    st.info("🟢 faible | 🟡 modéré | 🟠 soutenu | 🔴 fort | 🟣 sévère")

with tab3:
    components.html(radar_html(lat, lon), height=660)

with tab4:
    metar, err = fetch_metar(METAR_STATIONS[station])
    if err:
        st.warning(err)
    else:
        metar_card(metar)
    st.caption("METAR = observation aviation proche, utile mais moins locale que Rèves.")

with tab5:
    ds = daily_summary(avg_table)
    # Garder uniquement les jours où au moins une vraie température est disponible
    if "temp_max" in ds.columns:
        ds = ds[pd.to_numeric(ds["temp_max"], errors="coerce").notna()]
    ds = ds.head(days)
    st.dataframe(display_table(ds, 1), use_container_width=True, hide_index=True)

with tab6:
    st.subheader("Température et ressenti")
    st.line_chart(avg_table.set_index("time")[["temperature_2m","apparent_temperature"]])
    st.subheader("Pluie, vent et rafales")
    st.line_chart(avg_table.set_index("time")[["precipitation","wind_speed_10m","wind_gusts_10m"]])
    st.subheader("Scores convectifs")
    st.line_chart(avg_table.set_index("time")[["score_orage","score_grele","score_tornade_approximatif","risque_downburst","risque_supercellule"]])

with tab7:
    cols = ["time","modele","temperature_2m","apparent_temperature","precipitation","wind_gusts_10m","direction_vent","wind_direction_10m","dew_point_2m","pressure_msl","cape","freezing_level_height","score_orage","score_grele","score_tornade_approximatif","risque_downburst","risque_supercellule"]
    st.dataframe(display_table(all_models_table[[c for c in cols if c in all_models_table.columns]], 1), use_container_width=True, hide_index=True)
