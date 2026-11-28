"""Mesures récentes de Rèves et estimation du ressenti."""

from math import exp, isfinite
import re

import pandas as pd
import requests
import streamlit as st
from astral import Observer
from astral.sun import elevation

TZ = "Europe/Brussels"
METAR_URL = "https://aviationweather.gov/api/data/metar"


@st.cache_data(ttl=600, show_spinner=False)
def charleroi_reports():
    try:
        response = requests.get(
            METAR_URL, params={"ids": "EBCI", "format": "json", "hours": 2},
            timeout=4,
        )
        response.raise_for_status()
        reports = response.json() if response.status_code != 204 else []
        return reports if isinstance(reports, list) else []
    except (requests.RequestException, ValueError):
        return []


def station_feel(temp, report):
    wind_chill = report.get('windchill')
    try:
        if wind_chill is not None and isfinite(float(wind_chill)):
            return float(wind_chill) - 273.15, ''
    except (TypeError, ValueError, OverflowError):
        pass
    humidity, wind = report.get('humidity'), report.get('wind_speed')
    value = apparent_temperature(temp, humidity, wind)
    return value, 'Calculé à partir des relevés de Rèves' if value is not None else ''


def apparent_temperature(temp, humidity, wind):
    if humidity is None or wind is None:
        return None
    try:
        humidity, wind = float(humidity), float(wind)
        if 0 <= humidity <= 100 and isfinite(wind) and wind >= 0:
            vapor_pressure = humidity / 100 * 6.105 * exp(17.27 * temp / (237.7 + temp))
            return temp + 0.33 * vapor_pressure - 0.70 * wind - 4.00
    except (TypeError, ValueError, OverflowError, ZeroDivisionError):
        pass
    return None


def charleroi_feel(reports, temp, humidity, measured_at, now):
    """Estimate apparent temperature using nearby observed sustained wind."""
    candidates = []
    for report in reports:
        if report.get('icaoId') != 'EBCI':
            continue
        try:
            time = pd.Timestamp(report['obsTime'], unit='s', tz='UTC')
            speed = float(report['wspd'])
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if not (isfinite(speed) and speed >= 0 and speed != 999):
            continue
        delta = abs(time - measured_at)
        if pd.Timedelta(0) <= now - time <= pd.Timedelta(minutes=45) and delta <= pd.Timedelta(minutes=30):
            candidates.append((delta, -time.timestamp(), speed))
    if not candidates:
        return None, ''
    _, timestamp, speed = min(candidates)
    estimate = apparent_temperature(temp, humidity, speed * 1852 / 3600)
    observed_at = pd.Timestamp(-timestamp, unit='s', tz='UTC').tz_convert(now.tz)
    return estimate, f'Estimé · Vent de Charleroi à {observed_at:%H:%M}' if estimate is not None else ''


@st.cache_data(ttl=60, show_spinner=False)
def reves_reading():
    """Return the latest temperature and wind chill published by meteo-be.net."""
    try:
        response = requests.post(
            'https://meteo-be.net/api/graphql',
            json={'query': '{ station(slug: "reves") { recentData { temperature windchill date humidity wind_speed } } }'},
            timeout=10,
        )
        response.raise_for_status()
        data = response.json()['data']['station']['recentData']
        timestamp = pd.to_datetime(data['date'], utc=True, errors='coerce')
        temp = float(data['temperature']) - 273.15
        if pd.notna(timestamp) and isfinite(temp):
            try:
                feel, feel_source = station_feel(temp, data)
            except (TypeError, ValueError, OverflowError, ZeroDivisionError):
                feel, feel_source = None, ''
            return timestamp, temp, feel, feel_source, data.get('humidity')
    except (requests.RequestException, KeyError, TypeError, ValueError, OverflowError):
        pass
    return None


def current_reves():
    now = pd.Timestamp.now(tz=TZ)
    reading = reves_reading()
    if reading is None:
        return None
    measured_at, temperature, feel, _, humidity = reading
    if not pd.Timedelta(minutes=-2) <= now - measured_at <= pd.Timedelta(minutes=30):
        return None
    if feel is None and humidity is not None:
        feel, _ = charleroi_feel(charleroi_reports(), temperature, humidity, measured_at, now)
    return measured_at.tz_convert(TZ), temperature, feel


def banner_values(forecast, use_reves=True):
    reading = current_reves() if use_reves else None
    if reading is not None:
        measured_at, temperature, feel = reading
        heading = f"Relevé du {measured_at:%d/%m à %H:%M} · Heure belge"
        if feel is not None:
            return heading, degrees(temperature), f"Ressenti {degrees(feel)}"
        if forecast is not None and degrees(forecast.get("apparent_temperature")) != "—":
            return heading, degrees(temperature), f"Ressenti prévu {degrees(forecast.get('apparent_temperature'))}"
        return heading, degrees(temperature), "Ressenti indisponible"
    if forecast is None:
        return "Relevé de Rèves indisponible", "—", "Ressenti indisponible"
    forecast_time = pd.Timestamp(forecast["time"])
    heading = f"Prévision du {forecast_time:%d/%m à %H:%M} · Heure belge"
    return heading, degrees(forecast.get("temperature_2m")), f"Ressenti prévu {degrees(forecast.get('apparent_temperature'))}"


def degrees(value):
    try:
        temperature = float(value)
    except (ValueError, TypeError, OverflowError):
        return "—"
    return f"{temperature:.1f} °C".replace(".", ",") if isfinite(temperature) else "—"


def observed_weather(report):
    phenomena = report.get('wxString') or ''
    for pattern, code, description in (
        (r'TS', 95, 'Orage'),
        (r'FZ(?:RA|DZ)', 66, 'Précipitations verglaçantes'),
        (r'SN|SG', 73, 'Neige'),
        (r'PL|GR|GS', 77, 'Grésil ou grêle'),
        (r'RA', 61, 'Pluie'),
        (r'DZ', 51, 'Bruine'),
        (r'FG', 45, 'Brouillard'),
        (r'BR', 45, 'Brume'),
    ):
        if re.search(pattern, phenomena):
            return code, description
    if not phenomena:
        code = {
            'CLR': 0, 'SKC': 0, 'NCD': 0, 'FEW': 1,
            'SCT': 2, 'BKN': 2, 'OVC': 3,
        }.get(report.get('cover'))
        if code is not None:
            return code, None
    if not phenomena and report.get('cover') == 'CAVOK':
        return None, 'Bonne visibilité observée'
    return None


def banner_sky(latitude, longitude, forecast_icon, forecast_label, forecast_clear, now=None):
    if now is None:
        now = pd.Timestamp.now(tz=TZ)
    night = elevation(Observer(latitude, longitude), now.to_pydatetime()) < -0.833
    reports = []
    for report in charleroi_reports():
        try:
            observed_at = pd.Timestamp(report["obsTime"], unit="s", tz="UTC").tz_convert(TZ)
        except (KeyError, TypeError, ValueError, OverflowError):
            continue
        if pd.notna(observed_at) and pd.Timedelta(0) <= now - observed_at <= pd.Timedelta(minutes=75):
            reports.append((observed_at, report))
    if reports:
        observed_at, report = max(reports, key=lambda item: item[0])
        observation = observed_weather(report)
        if observation and observation[0] is not None:
            code, description = observation
            icons = {
                0: ("🌙", "Ciel serein") if night else ("☀️", "Ciel dégagé"),
                1: ("☁️" if night else "🌤️", "Peu nuageux"),
                2: ("☁️" if night else "⛅", "Partiellement nuageux"),
                3: ("☁️", "Couvert"),
                45: ("🌫️", "Brouillard"),
                51: ("🌦️", "Bruine"),
                61: ("🌧️", "Pluie"),
                66: ("🌧️", "Précipitations verglaçantes"),
                73: ("🌨️", "Neige"),
                77: ("🌨️", "Grésil ou grêle"),
                95: ("⛈️", "Orage"),
            }
            icon, label = icons[code]
            return icon, description or label, f"Observé à EBCI · {observed_at:%H:%M}"
                if forecast_label.strip().casefold() == "couvert":
        return "☁️", forecast_label, "Estimation du ciel"
    if night and forecast_clear:
        return "🌙", "Ciel serein", "Estimation du ciel"
    return forecast_icon, forecast_label, "Estimation du ciel" if forecast_label else ""
