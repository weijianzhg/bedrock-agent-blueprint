"""Local tests for agent tools and configuration.

These tests exercise the tool functions directly — no AWS credentials or
Bedrock access required. Run with:

    pytest tests/
"""

import json
import sys
from pathlib import Path

import pytest

# Add agent directory to the path so we can import tools
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "agents"))

from tools import calculate, get_weather, lookup_item  # noqa: E402


# -----------------------------------------------------------------------
# get_weather
# -----------------------------------------------------------------------


class TestGetWeather:
    def test_returns_success(self):
        result = get_weather(city="Seattle")
        assert result["status"] == "success"

    def test_contains_city_name(self):
        result = get_weather(city="Tokyo")
        text = result["content"][0]["text"]
        data = json.loads(text)
        assert data["city"] == "Tokyo"

    def test_celsius_default(self):
        result = get_weather(city="London")
        text = result["content"][0]["text"]
        data = json.loads(text)
        assert data["units"] == "celsius"

    def test_fahrenheit_units(self):
        result = get_weather(city="New York", units="fahrenheit")
        text = result["content"][0]["text"]
        data = json.loads(text)
        assert data["units"] == "fahrenheit"
        assert data["temperature"] == 72


# -----------------------------------------------------------------------
# calculate
# -----------------------------------------------------------------------


class TestCalculate:
    def test_basic_arithmetic(self):
        result = calculate(expression="2 + 3 * 4")
        assert result["status"] == "success"
        assert "14" in result["content"][0]["text"]

    def test_sqrt(self):
        result = calculate(expression="sqrt(144)")
        assert result["status"] == "success"
        assert "12" in result["content"][0]["text"]

    def test_pi(self):
        result = calculate(expression="round(pi, 4)")
        assert result["status"] == "success"
        assert "3.1416" in result["content"][0]["text"]

    def test_invalid_expression(self):
        result = calculate(expression="import os")
        assert result["status"] == "error"

    def test_undefined_name(self):
        result = calculate(expression="open('/etc/passwd')")
        assert result["status"] == "error"


# -----------------------------------------------------------------------
# lookup_item
# -----------------------------------------------------------------------


class TestLookupItem:
    def test_found_item(self):
        result = lookup_item(item_id="ITEM-001")
        assert result["status"] == "success"
        assert "Widget Pro" in result["content"][0]["text"]

    def test_not_found(self):
        result = lookup_item(item_id="ITEM-999")
        assert result["status"] == "not_found"

    def test_custom_database(self):
        result = lookup_item(item_id="ITEM-002", database="catalog")
        assert result["status"] == "success"
        assert "catalog" in result["content"][0]["text"]
