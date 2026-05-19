
import streamlit as st
import pandas as pd
import numpy as np
import requests
import plotly.express as px
import plotly.graph_objects as go

import base64
from pathlib import Path

@st.cache_data
def _icon_b64(filename):
    p = Path(__file__).parent / "icons" / filename
    return base64.b64encode(p.read_bytes()).decode("ascii")

def icon_img(filename, size=38):
    try:
        b64 = _icon_b64(filename)
        return (
            f"<span style='display:inline-flex;align-items:center;justify-content:center;"
            f"width:{size}px;height:{size}px;overflow:visible;'>"
            f"<img src='data:image/png;base64,{b64}' "
            f"style='max-width:{size}px;max-height:{size}px;object-fit:contain;vertical-align:middle;'>"
            f"</span>"
        )
    except Exception:
        return "☁️"


st.set_page_config(page_title="Météo Frasnes / Rèves Mobile", page_icon="🌦️", layout="centered", initial_sidebar_state="collapsed")

LAT, LON = 50.5384, 4.4523
MODELS = {
    "Best match": "best_match",
    "AROME France HD": "meteofrance_arome_france_hd",
    "AROME France": "meteofrance_arome_france",
    "ICON-D2": "icon_d2",
    "ICON-EU": "icon_eu",
    "ICON Global": "icon_global",
    "HARMONIE KNMI": "knmi_harmonie_arome_europe",
    "HARMONIE DMI": "dmi_harmonie_arome_europe",
    "GFS Global": "gfs_global",
    "ECMWF IFS": "ecmwf_ifs04",
}
HOURLY = ["temperature_2m","apparent_temperature","precipitation","precipitation_probability","weather_code","cloud_cover","wind_speed_10m","wind_gusts_10m","wind_direction_10m","relative_humidity_2m","dew_point_2m","pressure_msl","uv_index","cape","freezing_level_height","sunshine_duration"]
PERIODES_JOUR = [("Matin",6,12),("Après-midi",12,18),("Soirée",18,24)]
DAY_FR = {"Monday":"Lundi","Tuesday":"Mardi","Wednesday":"Mercredi","Thursday":"Jeudi","Friday":"Vendredi","Saturday":"Samedi","Sunday":"Dimanche"}
SHORT_FR = {"Monday":"lun","Tuesday":"mar","Wednesday":"mer","Thursday":"jeu","Friday":"ven","Saturday":"sam","Sunday":"dim"}

def fnum(x, default=0):
    try:
        if pd.isna(x): return default
        return float(x)
    except Exception:
        return default

def fr_day(dt):
    dt = pd.to_datetime(dt)
    return DAY_FR.get(dt.strftime("%A"), dt.strftime("%A"))

def fr_short(dt):
    dt = pd.to_datetime(dt)
    return SHORT_FR.get(dt.strftime("%A"), dt.strftime("%a").lower())

def compass(deg):
    try: deg = float(deg) % 360
    except Exception: return ""
    dirs = ["N","NE","E","SE","S","SO","O","NO"]
    return dirs[int((deg+22.5)//45)%8]

def weather_text(code):
    c=int(fnum(code,3))
    return {0:"Ciel clair",1:"Peu nuageux",2:"Partiellement nuageux",3:"Couvert",45:"Brume / brouillard",48:"Brouillard givrant",51:"Bruine faible",53:"Bruine",55:"Bruine forte",61:"Pluie faible",63:"Pluie",65:"Pluie forte",71:"Neige faible",73:"Neige",75:"Neige forte",80:"Averses faibles",81:"Averses",82:"Averses fortes",95:"Orage",96:"Orage avec grêle",99:"Orage violent"}.get(c,"Variable")

def fog_possible(row):
    c=int(fnum(row.get("weather_code",0)))
    hum=fnum(row.get("relative_humidity_2m",0)); wind=fnum(row.get("wind_speed_10m",0))
    temp=fnum(row.get("temperature_2m",0)); dew=fnum(row.get("dew_point_2m",0))
    return c in [45,48] or (hum>=95 and abs(temp-dew)<=1.4 and wind<=10)

def icon_for(row, storm=0):
    c=int(fnum(row.get("weather_code",3))); rain=fnum(row.get("precipitation",0)); cloud=fnum(row.get("cloud_cover",80))
    if fog_possible(row): return icon_img("brouillard.png")
    if fnum(storm)>=82 or c in [95,96,99]: return icon_img("orage.png")
    if c in [51,53,55]: return icon_img("bruine.png")
    if rain>=4.0 or c in [65,82]: return icon_img("pluie_forte.png")
    if rain>=1.0 or c in [63,81]: return icon_img("pluie_moderee.png")
    if rain>0.1 or c in [61,80]: return icon_img("pluie_faible.png")
    if c == 0 or cloud < 18: return icon_img("ciel_clair.png")
    if c == 1 or cloud < 38: return icon_img("peu_nuageux.png")
    if c == 2 or cloud < 72: return icon_img("partiellement_nuageux.png")
    return icon_img("tres_nuageux.png")

def code_level(score):
    s=fnum(score)
    if s<50: return "VERT","#15803d","Calme"
    if s<68: return "JAUNE","#ca8a04","À surveiller"
    if s<82: return "ORANGE","#f97316","Significatif"
    if s<94: return "ROUGE","#dc2626","Fort"
    return "VIOLET","#7c3aed","Sévère"

def css():
    st.markdown('''
<style>
.block-container{max-width:570px;padding-top:.8rem;padding-left:.7rem;padding-right:.7rem}
div[data-testid="stToolbar"]{display:none}
.hero{background:linear-gradient(160deg,#2563eb 0%,#1e3a8a 46%,#020617 100%);border-radius:30px;padding:22px;color:white;margin-bottom:14px;box-shadow:0 14px 30px rgba(0,0,0,.30)}
.card{background:#0f172a;border:1px solid #263244;color:white;border-radius:18px;padding:12px;text-align:center;margin-bottom:10px}
.soft{background:#111827;border:1px solid #263244;color:white;border-radius:18px;padding:14px;margin-bottom:10px}
.period{background:#0f172a;border:1px solid #263244;color:white;border-radius:18px;padding:14px;margin-bottom:10px}
.alert{color:white;border-radius:22px;padding:15px 16px;margin-bottom:14px;font-weight:850}
.pill{color:white;padding:5px 9px;border-radius:999px;font-weight:850;font-size:12px;display:inline-block}
.bigcode{font-size:30px;font-weight:950;letter-spacing:.02em}.small{font-size:12px;opacity:.86}a{color:#93c5fd!important}
</style>''', unsafe_allow_html=True)

def add_scores(d):
    d=d.copy()
    cape=d.get("cape",pd.Series(0,index=d.index)).fillna(0); precip=d.get("precipitation",pd.Series(0,index=d.index)).fillna(0)
    proba=d.get("precipitation_probability",pd.Series(0,index=d.index)).fillna(0); gust=d.get("wind_gusts_10m",pd.Series(0,index=d.index)).fillna(0)
    hum=d.get("relative_humidity_2m",pd.Series(0,index=d.index)).fillna(0); dew=d.get("dew_point_2m",pd.Series(0,index=d.index)).fillna(0)
    temp=d.get("temperature_2m",pd.Series(0,index=d.index)).fillna(0); freezing=d.get("freezing_level_height",pd.Series(2500,index=d.index)).replace(0,np.nan).fillna(2500)
    d["score_orage"]=((cape/46).clip(0,34)+(precip*5.2).clip(0,18)+((gust-44)*0.42).clip(0,22)+((hum-70)*0.14).clip(0,7)).clip(0,100).round(1)
    d["score_pluie_intense"]=((precip*9.5)+(proba*0.22)).clip(0,100).round(1)
    d["score_grele"]=((cape/68).clip(0,34)+((4300-freezing)/95).clip(0,20)+((gust-35)/4.2).clip(0,24)).clip(0,100).round(1)
    d["risque_downburst"]=(((gust-68)*0.95).clip(0,40)+((temp-27)*0.75).clip(0,15)+((100-hum)*0.14).clip(0,14)+(cape/230).clip(0,9)).clip(0,100).round(1)
    d["risque_supercellule"]=((cape/105).clip(0,30)+((gust-62)*0.55).clip(0,26)+((dew-15)*1.0).clip(0,16)+((4300-freezing)/230).clip(0,7)).clip(0,100).round(1)
    d["score_tornade_approximatif"]=((cape/140).clip(0,22)+((gust-65)*0.45).clip(0,25)+((dew-15)*1.15).clip(0,14)).clip(0,100).round(1)
    d["fog"]=d.apply(lambda r:1 if fog_possible(r) else 0,axis=1)
    d["temps"]=d["weather_code"].apply(weather_text); d["direction_vent"]=d["wind_direction_10m"].apply(compass)
    return d

def fetch_model(name, code):
    r=requests.get("https://api.open-meteo.com/v1/forecast", params={"latitude":LAT,"longitude":LON,"hourly":",".join(HOURLY),"forecast_days":8,"timezone":"Europe/Brussels","wind_speed_unit":"kmh","models":code}, timeout=25)
    r.raise_for_status(); df=pd.DataFrame(r.json().get("hourly",{}))
    if df.empty or "time" not in df: raise ValueError("pas de données")
    df["time"]=pd.to_datetime(df["time"])
    for c in HOURLY:
        if c in df.columns: df[c]=pd.to_numeric(df[c], errors="coerce")
    df["modele"]=name
    return df

@st.cache_data(ttl=600)
def load_multimodel(selected_models):
    frames=[]; errors=[]
    for name in selected_models:
        code = MODELS[name]
        try: frames.append(fetch_model(name,code))
        except Exception as e: errors.append(f"{name}: {str(e)[:70]}")
    if not frames: raise RuntimeError("Aucun modèle disponible")
    all_df=pd.concat(frames, ignore_index=True)
    num=[c for c in HOURLY if c in all_df.columns and c!="weather_code"]
    avg=all_df.groupby("time", as_index=False)[num].mean()
    if "weather_code" in all_df.columns:
        avg=avg.merge(all_df.groupby("time")["weather_code"].median().round().reset_index(), on="time", how="left")
    else:
        avg["weather_code"]=3
    avg=add_scores(avg)
    return avg, errors, sorted(all_df["modele"].dropna().unique().tolist())

def period_data_for_day(df,date,period,h1,h2):
    d=df.copy(); d["date"]=pd.to_datetime(d["time"]).dt.date; d["hour"]=pd.to_datetime(d["time"]).dt.hour
    if period=="Nuit":
        nd=(pd.to_datetime(date)+pd.Timedelta(days=1)).date()
        return d[(d["date"]==nd)&(d["hour"]>=0)&(d["hour"]<6)].copy()
    return d[(d["date"]==date)&(d["hour"]>=h1)&(d["hour"]<h2)].copy()

def summarize_period(part, period=""):
    if part.empty: return None
    mid=part.iloc[len(part)//2]
    tmin=fnum(part["temperature_2m"].min()); tmax=fnum(part["temperature_2m"].max()); tmean=fnum(part["temperature_2m"].mean())
    fmin=fnum(part["apparent_temperature"].min()); fmax=fnum(part["apparent_temperature"].max()); fmean=fnum(part["apparent_temperature"].mean())
    if "Après-midi" in period: temp,feel,label=tmax,fmax,"max"
    elif "Nuit" in period: temp,feel,label=tmin,fmin,"min"
    else: temp,feel,label=tmean,fmean,"moy"
    rain=fnum(part["precipitation"].sum()); proba=fnum(part["precipitation_probability"].max()); gust=fnum(part["wind_gusts_10m"].max())
    wind=fnum(part["wind_speed_10m"].mean()); storm=fnum(part["score_orage"].max()); hail=fnum(part["score_grele"].max())
    fog=int(part["fog"].max())==1; uv=fnum(part["uv_index"].max()); icon="🌫️" if fog else icon_for(mid,storm)
    ps=max(storm,hail*.9)
    if rain>=8 or (proba>=90 and rain>=3): ps=max(ps,55)
    if gust>=65: ps=max(ps,55)
    if gust>=80: ps=max(ps,70)
    code,color,lab=code_level(ps)
    return dict(icon=icon,temp=temp,feel=feel,temp_label=label,temp_min=tmin,temp_max=tmax,rain=rain,rain_proba=proba,gust=gust,wind=wind,storm=storm,hail=hail,fog=fog,uv=uv,code=code,color=color,label=lab)

def risk_24h(df):
    n=df.head(24); storm=fnum(n["score_orage"].max()); rain=fnum(n["score_pluie_intense"].max()); hail=fnum(n["score_grele"].max())
    down=fnum(n["risque_downburst"].max()); sup=fnum(n["risque_supercellule"].max()); tor=fnum(n["score_tornade_approximatif"].max()); gust=fnum(n["wind_gusts_10m"].max())
    return max(storm,rain*.55,hail*.9,down,sup,tor),storm,rain,hail,down,sup,tor,gust

def render_period_card(name,s,night=""):
    if not s:
        st.markdown(f'<div class="period"><b>{name}</b><br>—</div>',unsafe_allow_html=True); return
    fog=" · 🌫️ brume/brouillard possible" if s["fog"] else ""; title=f"{name} {night}".strip()
    html=f'''<div class="period"><div style="display:flex;align-items:center;justify-content:space-between;"><div><b>{title}</b><br><span class="small">{s["label"]}{fog}</span></div><div style="font-size:35px;">{s["icon"]}</div><span class="pill" style="background:{s["color"]};">{s["code"]}</span></div><div style="margin-top:8px;font-size:12px;">🌡️ {s["temp_label"]} {s["temp"]:.0f}°C · ressenti {s["feel"]:.0f}°C<br>↕️ min/max {s["temp_min"]:.0f}/{s["temp_max"]:.0f}°C<br>💧 {s["rain"]:.1f} mm · proba {s["rain_proba"]:.0f}%<br>💨 vent {s["wind"]:.0f} km/h · rafales {s["gust"]:.0f} km/h<br>⛈️ orage {s["storm"]:.0f}/100 · 🧊 grêle {s["hail"]:.0f}/100 · UV {s["uv"]:.1f}</div></div>'''
    st.markdown(html,unsafe_allow_html=True)

def render_home(df,models):
    now_ref = pd.Timestamp.now(tz="Europe/Brussels").tz_localize(None)
    future = df[df["time"] > now_ref].copy()
    if future.empty:
        r = df.iloc[0]
    else:
        r = future.iloc[0]
    storm=fnum(r["score_orage"]); ico=icon_for(r,storm); desc="Brume / brouillard possible" if fog_possible(r) else r["temps"]
    st.markdown(f'''<div class="hero"><div style="font-size:34px;font-weight:950;">Frasnes / Rèves</div><div style="opacity:.82;margin-bottom:15px;">Prochaine heure • {pd.to_datetime(r["time"]).strftime("%d/%m %H:%M")}</div><div style="display:flex;justify-content:space-between;align-items:center;"><div><div style="font-size:68px;font-weight:950;line-height:.92;">{fnum(r["temperature_2m"]):.1f}°C</div><div style="font-size:21px;">Ressenti {fnum(r["apparent_temperature"]):.1f}°C</div><div style="font-size:17px;margin-top:10px;">{desc}</div></div><div style="font-size:78px;">{ico}</div></div></div>''',unsafe_allow_html=True)
    c1,c2,c3=st.columns(3)
    with c1: st.markdown(f'<div class="card"><b>Pluie</b><br><span style="font-size:22px;font-weight:900;">{fnum(r["precipitation"]):.1f} mm</span></div>',unsafe_allow_html=True)
    with c2: st.markdown(f'<div class="card"><b>Vent</b><br><span style="font-size:22px;font-weight:900;">{fnum(r["wind_speed_10m"]):.0f} km/h</span></div>',unsafe_allow_html=True)
    with c3: st.markdown(f'<div class="card"><b>Rafales</b><br><span style="font-size:22px;font-weight:900;">{fnum(r["wind_gusts_10m"]):.0f} km/h</span></div>',unsafe_allow_html=True)
    score,storm,rain,hail,down,sup,tor,gust=risk_24h(df); code,color,label=code_level(score)
    st.markdown(f'<div class="alert" style="background:{color};"><div class="bigcode">CODE {code}</div>{label} sur 24h<br><span class="small">⛈️ {storm:.0f}/100 · 🌧️ {rain:.0f}/100 · 🧊 {hail:.0f}/100 · 🌀 {sup:.0f}/100 · 💨 {gust:.0f} km/h</span></div>',unsafe_allow_html=True)
    st.caption("Modèles utilisés : " + ", ".join(models))

def today_summary(df):
    today=pd.Timestamp.now(tz="Europe/Brussels").tz_localize(None).date()
    d=df[pd.to_datetime(df["time"]).dt.date==today].copy()
    if d.empty: return
    st.markdown(f'<div class="soft"><b>Résumé aujourd’hui</b><br>🌡️ min/max {fnum(d["temperature_2m"].min()):.0f}/{fnum(d["temperature_2m"].max()):.0f}°C · ressenti {fnum(d["apparent_temperature"].min()):.0f}/{fnum(d["apparent_temperature"].max()):.0f}°C<br>💧 {fnum(d["precipitation"].sum()):.1f} mm · 💨 rafales {fnum(d["wind_gusts_10m"].max()):.0f} km/h · ⛈️ {fnum(d["score_orage"].max()):.0f}/100</div>',unsafe_allow_html=True)

def today_periods(df):
    st.markdown("### Aujourd’hui")
    now_local = pd.Timestamp.now(tz="Europe/Brussels").tz_localize(None)
    today = now_local.date()
    current_hour = now_local.hour

    shown = 0

    for name, h1, h2 in PERIODES_JOUR:
        # Masque les périodes déjà terminées.
        if current_hour >= h2:
            continue
        render_period_card(name, summarize_period(period_data_for_day(df, today, name, h1, h2), name))
        shown += 1

    # Nuit à venir toujours affichée, même si on est en journée/soirée.
    tomorrow = pd.to_datetime(today) + pd.Timedelta(days=1)
    render_period_card("🌙 Nuit", summarize_period(period_data_for_day(df, today, "Nuit", 0, 6), "Nuit"), f"({fr_short(today)}→{fr_short(tomorrow)})")

    if shown == 0:
        st.caption("Les périodes de la journée sont passées. Affichage de la nuit à venir.")

def week_periods(df):
    st.markdown("### Semaine matin / après-midi / soirée / nuit")
    d=df.copy(); d["date"]=pd.to_datetime(d["time"]).dt.date
    for date in list(d["date"].drop_duplicates())[:7]:
        day=d[d["date"]==date].copy()
        dc,dcoll,dlab=code_level(max(fnum(day["score_orage"].max()),fnum(day["wind_gusts_10m"].max())-25,fnum(day["precipitation"].sum())*4))
        st.markdown(f"#### {fr_day(date)} {pd.to_datetime(date).strftime('%d/%m')}")
        st.markdown(f'<div class="soft" style="border-color:{dcoll};"><div style="display:flex;align-items:center;justify-content:space-between;"><div><b>Résumé du jour</b><br><span class="small">{dlab}</span></div><div style="font-size:24px;font-weight:950;">{fnum(day["temperature_2m"].min()):.0f}/{fnum(day["temperature_2m"].max()):.0f}°C</div><span class="pill" style="background:{dcoll};">{dc}</span></div><div style="margin-top:8px;font-size:13px;">Ressenti {fnum(day["apparent_temperature"].min()):.0f}/{fnum(day["apparent_temperature"].max()):.0f}°C · 💧 {fnum(day["precipitation"].sum()):.1f} mm · 💨 rafales {fnum(day["wind_gusts_10m"].max()):.0f} km/h · ⛈️ {fnum(day["score_orage"].max()):.0f}/100</div></div>',unsafe_allow_html=True)
        for name,h1,h2 in PERIODES_JOUR:
            s=summarize_period(period_data_for_day(df,date,name,h1,h2),name)
            if s: render_period_card(name,s)
        nd=pd.to_datetime(date)+pd.Timedelta(days=1)
        render_period_card("🌙 Nuit",summarize_period(period_data_for_day(df,date,"Nuit",0,6),"Nuit"),f"({fr_short(date)}→{fr_short(nd)})")

def alerts(df):
    st.markdown("### Alertes détaillées")
    score,storm,rain,hail,down,sup,tor,gust=risk_24h(df); c,col,lab=code_level(score)
    st.markdown(f'<div class="alert" style="background:{col};"><div class="bigcode">CODE {c}</div>{lab}</div>',unsafe_allow_html=True)
    for name,val in [("⛈️ Orage",storm),("🌧️ Pluie intense",rain),("🧊 Grêle",hail),("⬇️ Rafales descendantes",down),("🌀 Supercellule",sup),("🌪️ Tornade approximative",tor)]:
        cc,co,la=code_level(val); st.markdown(f'<div class="soft"><b>{name}</b><br><span style="font-size:24px;font-weight:950;">{val:.0f}/100</span><br><span class="pill" style="background:{co};">CODE {cc}</span> {la}</div>',unsafe_allow_html=True)
    st.markdown(f'<div class="soft"><b>🌫️ Brume / brouillard 24h</b><br><span style="font-size:23px;font-weight:900;">{"possible" if int(df.head(24)["fog"].sum()) else "non détecté"}</span></div>',unsafe_allow_html=True)

def radar():
    st.markdown("### Radar & liens utiles")
    st.link_button("📡 Radar Windy","https://www.windy.com/50.538/4.452")
    st.link_button("🌧️ Radar RainViewer","https://www.rainviewer.com/map.html?loc=50.5384,4.4523,8")
    st.link_button("🇧🇪 IRM Belgique","https://www.meteo.be")
    st.link_button("🌩️ Kachelmann","https://kachelmannwetter.com/be")

def details(df,errors):
    st.markdown("### Détails actuels"); r=df.iloc[0]; c1,c2=st.columns(2)
    with c1:
        st.metric("Humidité",f"{fnum(r['relative_humidity_2m']):.0f}%"); st.metric("Point de rosée",f"{fnum(r['dew_point_2m']):.1f}°C"); st.metric("Pression",f"{fnum(r['pressure_msl']):.1f} hPa"); st.metric("UV",f"{fnum(r['uv_index']):.1f}")
    with c2:
        st.metric("Vent",f"{fnum(r['wind_speed_10m']):.0f} km/h"); st.metric("Rafales",f"{fnum(r['wind_gusts_10m']):.0f} km/h"); st.metric("Direction",r["direction_vent"]); st.metric("CAPE",f"{fnum(r['cape']):.0f}")
    if errors:
        with st.expander("Modèles indisponibles"):
            for e in errors: st.write(e)




def daily_icon_from_summary(r):
    rain = fnum(r.get("rain", 0))
    sunshine_h = fnum(r.get("sunshine", 0)) / 3600
    cloud = fnum(r.get("cloud", 80))
    storm = fnum(r.get("storm", 0))
    fog = int(fnum(r.get("fog", 0))) == 1

    if storm >= 70:
        return icon_img("orage.png", 34)
    if rain >= 6:
        return icon_img("pluie_forte.png", 34)
    if rain >= 1.2:
        return icon_img("pluie_moderee.png", 34)
    if rain >= 0.2:
        return icon_img("pluie_faible.png", 34)
    if fog and (sunshine_h < 5 or cloud >= 80):
        return icon_img("brouillard.png", 34)
    if sunshine_h >= 12 and cloud < 30:
        return icon_img("ciel_clair.png", 34)
    if sunshine_h >= 9 and cloud < 55:
        return icon_img("peu_nuageux.png", 34)
    if sunshine_h >= 5 and cloud < 82:
        return icon_img("partiellement_nuageux.png", 34)
    return icon_img("tres_nuageux.png", 34)



def period_icon_for_summary(df, date, start_h, end_h):
    part = period_data_for_day(df, date, "Résumé", start_h, end_h)
    if part.empty:
        return icon_img("tres_nuageux.png", 32)

    rain = fnum(part["precipitation"].sum())
    storm = fnum(part["score_orage"].max())
    cloud = fnum(part["cloud_cover"].mean())
    sunshine = fnum(part["sunshine_duration"].sum()) / 3600 if "sunshine_duration" in part.columns else 0
    foggy = int(part["fog"].max()) == 1 if "fog" in part.columns else False
    code_med = int(round(fnum(part["weather_code"].median(), 3)))

    if storm >= 70 or code_med in [95, 96, 99]:
        return icon_img("orage.png", 32)
    if rain >= 4 or code_med in [65, 82]:
        return icon_img("pluie_forte.png", 32)
    if rain >= 1 or code_med in [63, 81]:
        return icon_img("pluie_moderee.png", 32)
    if code_med in [51, 53, 55]:
        return icon_img("bruine.png", 32)
    if rain > 0.1 or code_med in [61, 80]:
        return icon_img("pluie_faible.png", 32)
    if foggy and (sunshine < 2 or cloud >= 80):
        return icon_img("brouillard.png", 32)
    if code_med == 0 or cloud < 18:
        return icon_img("ciel_clair.png", 32)
    if code_med == 1 or cloud < 38:
        return icon_img("peu_nuageux.png", 32)
    if code_med == 2 or cloud < 72:
        return icon_img("partiellement_nuageux.png", 32)
    return icon_img("tres_nuageux.png", 32)


def summary_7_days(df):
    st.markdown("### Résumé 7 jours")
    st.markdown("""
<style>
/* TABLEAU_BORDURE_COULEUR */
.week-compact {
    background:#0f172a;
    border:2px solid var(--day-color, #263244);
    color:white;
    border-radius:20px;
    padding:0;
    margin-bottom:8px;
    overflow:hidden;
}
.week-row {
    display:grid;
    grid-template-columns: 60px 122px 66px 50px 44px 42px;
    align-items:center;
    font-size:13px;
    width:100%;
    min-height:70px;
}
.week-row > div {
    min-width:0;
    height:100%;
    display:flex;
    align-items:center;
    justify-content:center;
    padding:7px 4px;
    box-sizing:border-box;
}
.week-row > div:not(:last-child) {
    border-right:1px solid rgba(148,163,184,.22);
}
.week-row > div:first-child {
    flex-direction:column;
    align-items:center;
    justify-content:center;
    padding-left:4px;
    padding-right:4px;
    text-align:center;
}
.week-day {
    font-weight:900;
    font-size:15px;
    line-height:1.1;
    display:block;
    white-space:nowrap;
    text-align:center;
}
.week-row > div:first-child .week-small {
    font-size:12px;
    opacity:.95;
    line-height:1.15;
    white-space:nowrap;
    text-align:center;
}
.week-icon {
    display:flex;
    align-items:center;
    justify-content:center;
    gap:3px;
    overflow:visible;
}
.week-temp {
    font-size:20px;
    font-weight:950;
    white-space:nowrap;
    line-height:1;
    justify-content:center !important;
}
.week-small {
    font-size:12px;
    opacity:.96;
    white-space:nowrap;
    text-align:center;
}
.week-pill {
    display:none !important;
}
@media (max-width: 430px) {
    .week-row {
        grid-template-columns: 58px 118px 64px 48px 42px 40px;
        min-height:68px;
    }
    .week-row > div {
        padding:6px 3px;
    }
    .week-row > div:first-child {
        padding-left:3px;
        padding-right:3px;
    }
    .week-temp {font-size:19px;}
    .week-small {font-size:11.5px;}
    .week-icon {gap:2px;}
}
</style>
""", unsafe_allow_html=True)
                
    d = df.copy()
    d["date"] = pd.to_datetime(d["time"]).dt.date

    day = d.groupby("date", as_index=False).agg(
        temp_min=("temperature_2m", "min"),
        temp_max=("temperature_2m", "max"),
        feel_min=("apparent_temperature", "min"),
        feel_max=("apparent_temperature", "max"),
        rain=("precipitation", "sum"),
        sunshine=("sunshine_duration", "sum"),
        rain_proba=("precipitation_probability", "max"),
        gust=("wind_gusts_10m", "max"),
        wind=("wind_speed_10m", "mean"),
        storm=("score_orage", "max"),
        hail=("score_grele", "max"),
        supercell=("risque_supercellule", "max"),
        fog=("fog", "max"),
        code=("weather_code", "median"),
        cloud=("cloud_cover", "mean"),
    ).head(7)

    st.markdown("""
<style>
.week-compact {
    background:#0f172a;
    border:1px solid #263244;
    color:white;
    border-radius:18px;
    padding:8px 10px;
    margin-bottom:6px;
}
.week-row {
    display:grid;
    grid-template-columns: 40px 76px 48px 38px 38px 40px 22px;
    align-items:center;
    gap:4px;
    font-size:13px;
}
.week-day {
    font-weight:850;
}
.week-icon {
    font-size:25px;
    text-align:center;
    display:flex;
    align-items:center;
    justify-content:center;
    gap:3px;
    overflow:visible;
}
.week-temp {
    font-size:17px;
    font-weight:950;
}
.week-small {
    font-size:12px;
    opacity:.92;
}
.week-pill {
    width:16px;
    height:16px;
    border-radius:999px;
    display:inline-block;
    color:transparent;
    font-size:0;
    padding:0;
    text-align:center;
}
</style>
""", unsafe_allow_html=True)

    for _, r in day.iterrows():
        day_score = max(
            fnum(r["storm"]),
            fnum(r["hail"]) * 0.9,
            fnum(r["supercell"]),
            fnum(r["rain"]) * 4,
            fnum(r["gust"]) - 25,
        )

        code, color, label = code_level(day_score)
        ico = daily_icon_from_summary(r)
        ico_matin = period_icon_for_summary(df, r["date"], 6, 12)
        ico_aprem = period_icon_for_summary(df, r["date"], 12, 18)

        st.markdown(f"""
<div class="week-compact" style="--day-color:{color};">
  <div class="week-row">
    <div>
      <div class="week-day">{fr_short(r["date"]).capitalize()}</div>
      <div class="week-small">{pd.to_datetime(r["date"]).strftime("%d/%m")}</div>
    </div>
    <div class="week-icon">
      <span title="Matin">{ico_matin}</span>
      <span style="opacity:.55;font-size:12px;">→</span>
      <span title="Après-midi">{ico_aprem}</span>
    </div>
    <div class="week-temp">{fnum(r["temp_min"]):.0f}/{fnum(r["temp_max"]):.0f}°</div>
    <div class="week-small">☀️ {fnum(r["sunshine"]) / 3600:.0f}h</div>
    <div class="week-small">💧 {fnum(r["rain"]):.1f}</div>
    <div class="week-small">💨 {fnum(r["gust"]):.0f}</div></div>
</div>
""", unsafe_allow_html=True)

    st.caption("Format compact : min/max, soleil réel estimé, pluie cumulée, rafales max et code couleur du jour.")


def graphs(df):
    st.markdown("### 📈 Graphiques")

    horizon = st.radio(
        "Horizon",
        ["48h", "7 jours"],
        horizontal=True,
        index=0
    )

    graph_df = df.copy()
    if horizon == "48h":
        graph_df = graph_df.head(48)

    # Axe X plus lisible : affiche chaque jour en bas du graphique.
    xaxis_days = dict(
        tickformat="%a %d/%m",
        dtick=86400000,
        tickangle=0,
        showgrid=True,
    )

    # Température et ressenti
    fig_temp = go.Figure()
    fig_temp.add_trace(go.Scatter(
        x=graph_df["time"],
        y=graph_df["temperature_2m"],
        mode="lines",
        name="Température",
        line=dict(color="#38bdf8", width=4)
    ))
    fig_temp.add_trace(go.Scatter(
        x=graph_df["time"],
        y=graph_df["apparent_temperature"],
        mode="lines",
        name="Ressenti",
        line=dict(color="#f59e0b", width=2)
    ))
    fig_temp.update_layout(
        title="Température & ressenti",
        height=310,
        margin=dict(l=10, r=10, t=45, b=10),
        legend=dict(orientation="h"),
        xaxis=xaxis_days,
    )
    st.plotly_chart(fig_temp, use_container_width=True)

    # Ensoleillement
    if "sunshine_duration" in graph_df.columns:
        fig_sun = go.Figure()
        sun_df = graph_df.copy()
        sun_df["sunshine_hours"] = sun_df["sunshine_duration"] / 3600
        fig_sun.add_trace(go.Bar(
            x=sun_df["time"],
            y=sun_df["sunshine_hours"],
            name="Ensoleillement",
            marker=dict(color="#facc15")
        ))
        fig_sun.update_layout(
            title="Durée de soleil réel estimé",
            height=280,
            margin=dict(l=10, r=10, t=45, b=10),
            showlegend=False,
            xaxis=xaxis_days,
            yaxis_title="heures"
        )
        st.plotly_chart(fig_sun, use_container_width=True)

    # Pluie
    fig_rain = go.Figure()
    fig_rain.add_trace(go.Bar(
        x=graph_df["time"],
        y=graph_df["precipitation"],
        name="Pluie mm"
    ))
    fig_rain.update_layout(
        title="Pluie prévue",
        height=280,
        margin=dict(l=10, r=10, t=45, b=10),
        showlegend=False,
        xaxis=xaxis_days,
    )
    st.plotly_chart(fig_rain, use_container_width=True)

    # Vent / rafales
    fig_wind = go.Figure()
    fig_wind.add_trace(go.Scatter(
        x=graph_df["time"],
        y=graph_df["wind_speed_10m"],
        mode="lines",
        name="Vent"
    ))
    fig_wind.add_trace(go.Scatter(
        x=graph_df["time"],
        y=graph_df["wind_gusts_10m"],
        mode="lines",
        name="Rafales"
    ))
    fig_wind.update_layout(
        title="Vent & rafales",
        height=310,
        margin=dict(l=10, r=10, t=45, b=10),
        legend=dict(orientation="h"),
        xaxis=xaxis_days,
    )
    st.plotly_chart(fig_wind, use_container_width=True)

    # Orages / CAPE
    fig_storm = go.Figure()
    fig_storm.add_trace(go.Scatter(
        x=graph_df["time"],
        y=graph_df["score_orage"],
        mode="lines",
        name="Score orage"
    ))
    fig_storm.add_trace(go.Scatter(
        x=graph_df["time"],
        y=graph_df["risque_supercellule"],
        mode="lines",
        name="Supercellule"
    ))
    fig_storm.add_trace(go.Scatter(
        x=graph_df["time"],
        y=graph_df["score_grele"],
        mode="lines",
        name="Grêle"
    ))
    fig_storm.update_layout(
        title="Indices orageux",
        height=320,
        margin=dict(l=10, r=10, t=45, b=10),
        legend=dict(orientation="h"),
        yaxis=dict(range=[0, 100]),
        xaxis=xaxis_days,
    )
    st.plotly_chart(fig_storm, use_container_width=True)

    fig_cape = go.Figure()
    fig_cape.add_trace(go.Scatter(
        x=graph_df["time"],
        y=graph_df["cape"],
        mode="lines",
        name="CAPE"
    ))
    fig_cape.update_layout(
        title="CAPE",
        height=280,
        margin=dict(l=10, r=10, t=45, b=10),
        showlegend=False,
        xaxis=xaxis_days,
    )
    st.plotly_chart(fig_cape, use_container_width=True)


css()

st.markdown("### Modèles météo")
st.caption("Choisis un modèle seul ou plusieurs modèles pour faire une moyenne.")

default_models = ["Best match", "ECMWF IFS", "ICON-EU", "AROME France HD"]
selected_models = st.multiselect(
    "Sélection des modèles",
    list(MODELS.keys()),
    default=[m for m in default_models if m in MODELS],
)

if not selected_models:
    selected_models = ["Best match"]

try:
    df,errors,model_names=load_multimodel(selected_models)
    now=pd.Timestamp.now(tz="Europe/Brussels").tz_localize(None)
    df=df[df["time"]>=(now-pd.Timedelta(hours=1))].copy()
    tab_home,tab_week,tab_summary,tab_alerts,tab_graphs,tab_radar,tab_details=st.tabs(["🏠 Jour","📅 Semaine","🗓️ Résumé 7j","⚠️ Alertes","📈 Graphiques","🌧️ Radar","📊 Détails"])
    with tab_home:
        render_home(df,model_names); today_summary(df); today_periods(df); st.caption("V13.2 — soleil, pluie faible/modérée/forte et résumé compact.")
    with tab_week: week_periods(df)
    with tab_summary: summary_7_days(df)
    with tab_alerts: alerts(df)
    with tab_graphs: graphs(df)
    with tab_radar: radar()
    with tab_details: details(df,errors)
except Exception as e:
    st.error("Erreur de chargement météo")
    st.code(str(e))
