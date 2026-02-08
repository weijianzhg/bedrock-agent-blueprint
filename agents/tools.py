"""Custom tools for the tool-use agent.

Each tool is a plain Python function decorated with @tool. Strands automatically
extracts the tool name, description, and parameter schema from the function
signature and docstring — no manual JSON schema needed.

Replace these example tools with your own domain-specific logic.
"""

import json
import math
from datetime import datetime, timezone
from typing import Optional

from strands import tool


@tool
def get_weather(city: str, units: str = "celsius") -> dict:
    """Get the current weather for a city.

    Args:
        city: The name of the city to get weather for.
        units: Temperature units — either "celsius" or "fahrenheit". Defaults to celsius.

    Returns:
        A dictionary containing the weather information.
    """
    # In a real agent, this would call a weather API.
    # This stub returns plausible data so you can test the tool-calling flow.
    mock_data = {
        "city": city,
        "temperature": 22 if units == "celsius" else 72,
        "units": units,
        "condition": "partly cloudy",
        "humidity": 65,
        "wind_speed_kmh": 12,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
    }
    return {
        "status": "success",
        "content": [{"text": json.dumps(mock_data, indent=2)}],
    }


@tool
def calculate(expression: str) -> dict:
    """Evaluate a mathematical expression safely.

    Supports basic arithmetic (+, -, *, /), exponentiation (**), and common
    math functions (sqrt, sin, cos, log, pi, e). Does NOT execute arbitrary
    Python code.

    Args:
        expression: A mathematical expression to evaluate, e.g. "sqrt(144) + 3 * 2".

    Returns:
        A dictionary containing the result of the calculation.
    """
    # Provide a safe subset of math functions
    allowed_names = {
        "sqrt": math.sqrt,
        "sin": math.sin,
        "cos": math.cos,
        "tan": math.tan,
        "log": math.log,
        "log10": math.log10,
        "log2": math.log2,
        "pi": math.pi,
        "e": math.e,
        "abs": abs,
        "round": round,
        "pow": pow,
        "floor": math.floor,
        "ceil": math.ceil,
    }
    try:
        result = eval(expression, {"__builtins__": {}}, allowed_names)  # noqa: S307
        return {
            "status": "success",
            "content": [{"text": f"{expression} = {result}"}],
        }
    except Exception as exc:
        return {
            "status": "error",
            "content": [{"text": f"Could not evaluate '{expression}': {exc}"}],
        }


@tool
def lookup_item(item_id: str, database: Optional[str] = "inventory") -> dict:
    """Look up an item in a database by its ID.

    This is a stub that demonstrates how a tool might integrate with an
    external data source (DynamoDB, RDS, an API, etc.). Replace the mock
    data with real queries for your use case.

    Args:
        item_id: The unique identifier of the item to look up.
        database: Which database to search. Defaults to "inventory".

    Returns:
        A dictionary containing the item details.
    """
    # Mock data — swap this for a real DB call
    mock_items = {
        "ITEM-001": {
            "id": "ITEM-001",
            "name": "Widget Pro",
            "price": 29.99,
            "in_stock": True,
        },
        "ITEM-002": {
            "id": "ITEM-002",
            "name": "Gadget Max",
            "price": 49.99,
            "in_stock": False,
        },
    }

    item = mock_items.get(item_id)
    if item:
        return {
            "status": "success",
            "content": [
                {"text": f"Found in {database}: {json.dumps(item, indent=2)}"}
            ],
        }
    return {
        "status": "not_found",
        "content": [
            {"text": f"No item with ID '{item_id}' found in {database}."}
        ],
    }
