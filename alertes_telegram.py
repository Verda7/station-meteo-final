
import json
import os
from datetime import datetime
import requests
import pandas as pd
import numpy as np

CONFIG_FILE = "config_alertes.json"
STATE_FILE = "alertes_state.json"

LAT = 50.5384
LON = 4.4523

HOURLY = [
    "temperature_2m",
    "apparent_temperature",
    "precipitation",
    "precipitation_probability",
    "wind_speed_10m",
    "wind_gusts_10m",
    "relative_humidity_2m",
    "dew_point_2m",
    "cape",
    "freezing_level_height",
]

def load_config():
    with open(CONFIG_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def load_state():
    if not os.path.exists(STATE_FILE):
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)

def send_telegram(token, chat_id, text):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    r = requests.post(url, data=payload, timeout=20)
    r.raise_for_status()

def fetch_forecast(hours=48):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": LAT,
        "longitude": LON,
        "hourly": ",".join(HOURLY),
        "forecast_days": 3,
        "timezone": "Europe/Brussels",
        "wind_speed_unit": "kmh",
    }
    r = requests.get(url, params=params, timeout=25)
    r.raise_for_status()
    data = r.json()["hourly"]
    df = pd.DataFrame(data)
    df["time"] = pd.to_datetime(df["time"])
    now = pd.Timestamp.now(tz="Europe/Brussels").tz_localize(None)
    df = df[df["time"] >= now].head(hours).copy()
    for col in HOURLY:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return compute_scores(df)

def compute_scores(df):
    d = df.copy()
    for col in HOURLY:
        if col not in d.columns:
            d[col] = np.nan

    cape = d["cape"].fillna(0)
    precip = d["precipitation"].fillna(0)
    proba = d["precipitation_probability"].fillna(0)
    gust = d["wind_gusts_10m"].fillna(0)
    humidity = d["relative_humidity_2m"].fillna(0)
    dew = d["dew_point_2m"].fillna(0)
    temp = d["temperature_2m"].fillna(0)
    freezing = d["freezing_level_height"].replace(0, np.nan).fillna(2500)

    d["score_orage"] = (
        (cape / 30).clip(0,45)
        + (precip * 8).clip(0,30)
        + ((gust - 30) * 0.7).clip(0,25)
        + ((humidity - 55) * 0.25).clip(0,10)
    ).clip(0,100).round(1)

    d["score_pluie_intense"] = ((precip * 15) + (proba * 0.4)).clip(0,100).round(1)

    d["score_grele"] = (
        (cape / 45).clip(0,45)
        + ((4500 - freezing) / 60).clip(0,25)
        + (gust / 3).clip(0,30)
    ).clip(0,100).round(1)

    d["grele_estimee_cm"] = np.where(d["score_grele"] < 35, 0, ((d["score_grele"] - 30) / 18).clip(0,6)).round(1)

    d["score_tornade_approximatif"] = (
        (cape / 80).clip(0,30)
        + ((gust - 45) * 0.8).clip(0,35)
        + ((dew - 12) * 2).clip(0,20)
    ).clip(0,100).round(1)

    d["risque_downburst"] = (
        ((gust - 50) * 1.2).clip(0,45)
        + ((temp - 20) * 1.2).clip(0,25)
        + ((100 - humidity) * 0.25).clip(0,20)
        + (cape / 120).clip(0,10)
    ).clip(0,100).round(1)

    d["risque_supercellule"] = (
        (cape / 60).clip(0,35)
        + ((gust - 45) * 0.8).clip(0,35)
        + ((dew - 12) * 1.5).clip(0,20)
        + ((4500 - freezing) / 150).clip(0,10)
    ).clip(0,100).round(1)

    return d

def max_row(df, column):
    if column not in df.columns or df[column].dropna().empty:
        return None
    idx = df[column].idxmax()
    return df.loc[idx]

def check_alerts(df, cfg):
    thresholds = cfg["thresholds"]
    alerts = []

    rules = [
        ("⛈️ Orage fort", "score_orage", thresholds["score_orage"]),
        ("🌧️ Pluie intense", "score_pluie_intense", thresholds["score_pluie_intense"]),
        ("🧊 Grêle", "score_grele", thresholds["score_grele"]),
        ("🌪️ Rotation / tornade possible", "score_tornade_approximatif", thresholds["score_tornade_approximatif"]),
        ("⬇️ Downburst / rafales descendantes", "risque_downburst", thresholds["risque_downburst"]),
        ("🌀 Supercellule possible", "risque_supercellule", thresholds["risque_supercellule"]),
        ("💨 Rafales fortes", "wind_gusts_10m", thresholds["wind_gusts_10m"]),
    ]

    for title, col, threshold in rules:
        row = max_row(df, col)
        if row is None:
            continue
        val = float(row[col])
        if val >= threshold:
            alerts.append((title, col, val, row))

    return alerts

def build_message(alerts):
    now = datetime.now().strftime("%d/%m/%Y à %H:%M")
    lines = [
        "🚨 <b>ALERTE MÉTÉO — Frasnes / Rèves</b>",
        f"<i>Analyse automatique du {now}</i>",
        "",
    ]

    for title, col, val, row in alerts:
        time_txt = pd.to_datetime(row["time"]).strftime("%d/%m %H:%M")
        lines.append(title)
        if col.startswith("score") or col.startswith("risque"):
            lines.append(f"• Valeur max : <b>{val:.1f}/100</b>")
        else:
            lines.append(f"• Valeur max : <b>{val:.1f} km/h</b>")
        lines.append(f"• Échéance : <b>{time_txt}</b>")
        lines.append(
            f"• Contexte : orage {row.get('score_orage',0):.1f}/100, "
            f"grêle {row.get('score_grele',0):.1f}/100, "
            f"supercellule {row.get('risque_supercellule',0):.1f}/100, "
            f"rafales {row.get('wind_gusts_10m',0):.0f} km/h"
        )
        if row.get("grele_estimee_cm", 0) > 0:
            lines.append(f"• Grêle estimée : <b>{row.get('grele_estimee_cm',0):.1f} cm</b>")
        lines.append("")

    lines.append("⚠️ Indices automatiques indicatifs, à confirmer avec radar/IRM/METAR.")
    return "\n".join(lines)

def main(test=False):
    cfg = load_config()
    token = cfg["telegram_bot_token"]
    chat_id = cfg["telegram_chat_id"]

    if token.startswith("TON_") or chat_id.startswith("TON_"):
        raise SystemExit("Configure d'abord config_alertes.json avec ton token Telegram et ton chat_id.")

    if test:
        send_telegram(token, chat_id, "✅ Test alerte météo OK — Frasnes / Rèves")
        print("Message test envoyé.")
        return

    df = fetch_forecast(hours=int(cfg.get("lookahead_hours", 48)))
    alerts = check_alerts(df, cfg)

    if not alerts:
        print("Aucune alerte à envoyer.")
        return

    cooldown_h = int(cfg.get("cooldown_hours", 3))
    state = load_state()
    now = datetime.now()
    filtered = []

    for a in alerts:
        title, col, val, row = a
        key = col
        last = state.get(key)
        send = True
        if last:
            try:
                last_dt = datetime.fromisoformat(last)
                if (now - last_dt).total_seconds() < cooldown_h * 3600:
                    send = False
            except Exception:
                pass
        if send:
            filtered.append(a)
            state[key] = now.isoformat()

    if not filtered:
        print("Alertes détectées mais ignorées par anti-spam cooldown.")
        return

    message = build_message(filtered)
    send_telegram(token, chat_id, message)
    save_state(state)
    print("Alerte envoyée.")

if __name__ == "__main__":
    import sys
    main(test="--test" in sys.argv)
