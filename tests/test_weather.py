"""Unit tests for the Open-Meteo weather client."""

from __future__ import annotations

import httpx
import pytest
import respx

from tollbooth_sample import weather


@respx.mock
async def test_get_current_success():
    """get_current returns structured weather data."""
    respx.get("https://api.open-meteo.com/v1/forecast").mock(
        return_value=httpx.Response(
            200,
            json={
                "latitude": 40.71,
                "longitude": -74.01,
                "timezone": "America/New_York",
                "current_weather": {
                    "temperature": 22.5,
                    "windspeed": 12.3,
                    "winddirection": 180,
                    "weathercode": 0,
                    "time": "2026-03-04T12:00",
                },
            },
        )
    )

    result = await weather.get_current(40.71, -74.01)

    assert result["success"] is True
    assert result["current_weather"]["temperature"] == 22.5
    assert result["latitude"] == 40.71


@respx.mock
async def test_get_forecast_success():
    """get_forecast returns daily forecast arrays."""
    respx.get("https://api.open-meteo.com/v1/forecast").mock(
        return_value=httpx.Response(
            200,
            json={
                "latitude": 48.85,
                "longitude": 2.35,
                "timezone": "Europe/Paris",
                "daily": {
                    "time": ["2026-03-04", "2026-03-05"],
                    "temperature_2m_max": [18.0, 20.0],
                    "temperature_2m_min": [10.0, 12.0],
                    "precipitation_sum": [0.0, 2.5],
                    "weathercode": [0, 3],
                },
                "daily_units": {
                    "temperature_2m_max": "°C",
                    "temperature_2m_min": "°C",
                    "precipitation_sum": "mm",
                },
            },
        )
    )

    result = await weather.get_forecast(48.85, 2.35, days=2)

    assert result["success"] is True
    assert result["forecast_days"] == 2
    assert len(result["daily"]["time"]) == 2


@respx.mock
async def test_get_forecast_clamps_days():
    """get_forecast clamps days to [1, 16]."""
    respx.get("https://api.open-meteo.com/v1/forecast").mock(
        return_value=httpx.Response(
            200,
            json={
                "latitude": 0,
                "longitude": 0,
                "timezone": "UTC",
                "daily": {"time": []},
                "daily_units": {},
            },
        )
    )

    result = await weather.get_forecast(0, 0, days=999)
    assert result["forecast_days"] == 16


@respx.mock
async def test_get_historical_success():
    """get_historical returns archive data."""
    respx.get("https://archive-api.open-meteo.com/v1/archive").mock(
        return_value=httpx.Response(
            200,
            json={
                "latitude": 35.68,
                "longitude": 139.69,
                "timezone": "Asia/Tokyo",
                "daily": {
                    "time": ["2025-01-01"],
                    "temperature_2m_max": [8.0],
                    "temperature_2m_min": [2.0],
                    "precipitation_sum": [0.0],
                    "weathercode": [1],
                },
                "daily_units": {},
            },
        )
    )

    result = await weather.get_historical(35.68, 139.69, "2025-01-01", "2025-01-01")

    assert result["success"] is True
    assert result["start_date"] == "2025-01-01"
    assert result["end_date"] == "2025-01-01"


@respx.mock
async def test_get_current_http_error():
    """get_current raises on non-200 response."""
    respx.get("https://api.open-meteo.com/v1/forecast").mock(
        return_value=httpx.Response(500, text="Internal Server Error")
    )

    with pytest.raises(httpx.HTTPStatusError):
        await weather.get_current(0, 0)
