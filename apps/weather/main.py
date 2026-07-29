"""Stello Weather — a NiceGUI 7-day forecast by US ZIP code.

A plain stello application (it doesn't use the stello library — it's just a tool you can
run with ``stello run weather``). Enter a ZIP code and it shows a 7-day forecast, using
two free, key-less APIs: Zippopotam.us (ZIP → lat/lon) and Open-Meteo (forecast).

Set STELLO_WEATHER_NO_SHOW=1 to not auto-open a browser (used by tests).
"""

from __future__ import annotations

import argparse
import os
from datetime import date

import httpx
from nicegui import ui

# WMO weather codes -> (emoji, description). https://open-meteo.com/en/docs
WEATHER_CODES: dict[int, tuple[str, str]] = {
    0: ("☀️", "Clear"),
    1: ("🌤️", "Mainly clear"),
    2: ("⛅", "Partly cloudy"),
    3: ("☁️", "Overcast"),
    45: ("🌫️", "Fog"),
    48: ("🌫️", "Rime fog"),
    51: ("🌦️", "Light drizzle"),
    53: ("🌦️", "Drizzle"),
    55: ("🌦️", "Heavy drizzle"),
    61: ("🌧️", "Light rain"),
    63: ("🌧️", "Rain"),
    65: ("🌧️", "Heavy rain"),
    66: ("🌧️", "Freezing rain"),
    67: ("🌧️", "Freezing rain"),
    71: ("🌨️", "Light snow"),
    73: ("🌨️", "Snow"),
    75: ("🌨️", "Heavy snow"),
    77: ("🌨️", "Snow grains"),
    80: ("🌦️", "Light showers"),
    81: ("🌦️", "Showers"),
    82: ("⛈️", "Violent showers"),
    85: ("🌨️", "Snow showers"),
    86: ("🌨️", "Snow showers"),
    95: ("⛈️", "Thunderstorm"),
    96: ("⛈️", "Thunderstorm, hail"),
    99: ("⛈️", "Thunderstorm, hail"),
}


def describe(code: int) -> tuple[str, str]:
    """Emoji + text for a WMO weather code."""
    return WEATHER_CODES.get(code, ("❓", f"Code {code}"))


state: dict = {"location": None, "daily": None, "error": None}


async def _fetch(zip_code: str) -> tuple[str, dict]:
    async with httpx.AsyncClient(timeout=10) as client:
        geo = await client.get(f"https://api.zippopotam.us/us/{zip_code.strip()}")
        geo.raise_for_status()
        place = geo.json()["places"][0]
        location = f"{place['place name']}, {place['state abbreviation']} {zip_code.strip()}"
        forecast = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": place["latitude"],
                "longitude": place["longitude"],
                "daily": "weathercode,temperature_2m_max,temperature_2m_min",
                "temperature_unit": "fahrenheit",
                "timezone": "auto",
                "forecast_days": 7,
            },
        )
        forecast.raise_for_status()
        return location, forecast.json()["daily"]


async def load(zip_code: str) -> None:
    zip_code = (zip_code or "").strip()
    if not (zip_code.isdigit() and len(zip_code) == 5):
        state.update(error="Enter a 5-digit US ZIP code.", daily=None, location=None)
        forecast_panel.refresh()
        return
    try:
        location, daily = await _fetch(zip_code)
        state.update(location=location, daily=daily, error=None)
    except Exception as exc:  # noqa: BLE001 - show the failure in the UI
        state.update(error=f"Could not load forecast for {zip_code}: {exc}", daily=None, location=None)
    forecast_panel.refresh()


@ui.refreshable
def forecast_panel() -> None:
    if state["error"]:
        ui.label(state["error"]).classes("text-red-500")
        return
    daily = state["daily"]
    if not daily:
        ui.label("Loading…").classes("text-gray-500")
        return
    ui.label(state["location"]).classes("text-lg font-bold")
    with ui.row().classes("gap-2 flex-wrap"):
        times = daily["time"]
        highs = daily["temperature_2m_max"]
        lows = daily["temperature_2m_min"]
        codes = daily["weathercode"]
        for day, high, low, code in zip(times, highs, lows, codes):
            emoji, text = describe(int(code))
            d = date.fromisoformat(day)
            with ui.card().classes("items-center w-28"):
                ui.label(d.strftime("%a")).classes("font-bold")
                ui.label(d.strftime("%m/%d")).classes("text-xs text-gray-500")
                ui.label(emoji).classes("text-4xl")
                ui.label(f"{round(high)}° / {round(low)}°")
                ui.label(text).classes("text-xs text-center")


def build(default_zip: str) -> None:
    ui.label("stello · weather").classes("text-2xl font-bold")
    with ui.row().classes("items-center gap-2"):
        zip_input = ui.input("US ZIP code", value=default_zip).props("outlined dense")
        ui.button("Get forecast", on_click=lambda: load(zip_input.value))
    forecast_panel()
    ui.timer(0.1, lambda: load(default_zip), once=True)  # load the default on startup


def main() -> None:
    parser = argparse.ArgumentParser(description="Stello weather (web UI).")
    parser.add_argument("--port", type=int, default=8090, help="port to serve on")
    parser.add_argument("--zip", default="80302", help="ZIP code to show first")
    args = parser.parse_args()
    build(default_zip=args.zip)
    ui.run(
        port=args.port,
        title="stello weather",
        reload=False,
        show=not os.environ.get("STELLO_WEATHER_NO_SHOW"),
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
