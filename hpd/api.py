# hpd/api.py

import httpx
import json
from typing import List, Optional
from .auth import generate_auth_header
from .models import Product

BASE_URL = "https://api.hpd.ca"

# Helper to send GET requests
def get(endpoint: str, query: str = ""):
    url = f"{BASE_URL}{endpoint}{query}"
    headers = {
        "Authorization": generate_auth_header("GET", endpoint, query)
    }
    try:
        response = httpx.get(url, headers=headers, timeout=60.0)
        response.raise_for_status()

        content_type = response.headers.get("content-type", "")
        if "application/json" in content_type:
            return response.json()
        else:
            return response.text  # return raw HTML or plain text
    except httpx.RequestError as e:
        print(f"[ERROR] Request failed: {e}")
        return None

# Helper to send POST requests
def post(endpoint: str, data: dict):
    body_str = json.dumps(data, sort_keys=True, separators=(",", ":"))
    query = ""
    headers = {
        "Authorization": generate_auth_header("POST", endpoint, query, body_str),
        "Content-Type": "application/json"
    }
    url = f"{BASE_URL}{endpoint}"
    response = httpx.post(url, headers=headers, json=data, timeout=60.0)
    response.raise_for_status()
    return response.json()

# API Function: GET /
def get_root():
    return get("/")

# API Function: GET /get_inventory
def get_inventory(parts: List[str]):
    query = "?" + "&".join([f"part={p}" for p in parts])
    return get("/get_inventory", query)

# API Function: GET /get_parts_on_order
def get_parts_on_order():
    return get("/get_parts_on_order")

# API Function: POST /place_order
def place_order(order_payload: dict):
    return post("/place_order", order_payload)

# API Function: GET /get_tracking_info
def get_tracking_info(invoice: Optional[str] = None, order: Optional[str] = None):
    if invoice and order:
        raise ValueError("Provide either invoice or order, not both.")
    if invoice:
        query = f"?invoice={invoice}"
    elif order:
        query = f"?order={order}"
    else:
        raise ValueError("Must provide invoice or order.")
    return get("/get_tracking_info", query)

# API Function: GET /full_catalog
def get_full_catalog() -> list[Product]:
    response = get("/full_catalog")

    if not response.get("success"):
        raise ValueError(f"API Error: {response.get('errors')}")

    columns = response["result"]["columns"]
    rows = response["result"]["rows"]
    
    # Map each row into a Product dataclass
    return [Product(**dict(zip(columns, row))) for row in rows]

def unwrap_result(response: dict):
    if response.get("success"):
        return response["result"]
    else:
        raise ValueError(f"API Error: {response.get('errors')}")