# main.py
import os
import json
from typing import Optional

import ee
from fastapi import FastAPI
from pydantic import BaseModel
from google.oauth2 import service_account
from openai import OpenAI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from gee_functions import compare_dw_abudhabi_years

# -------- FastAPI app --------
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# serve frontend folder at /app
app.mount("/app", StaticFiles(directory="frontend", html=True), name="frontend")

# -------- Earth Engine initialization --------
SCOPES = [
    "https://www.googleapis.com/auth/earthengine",
    "https://www.googleapis.com/auth/devstorage.read_write",
]

KEY_FILE = "gee-backend-key.json"  # local dev only; do NOT commit

def init_earth_engine():
    if "GEE_SERVICE_ACCOUNT_JSON" in os.environ:
        service_account_info = json.loads(os.environ["GEE_SERVICE_ACCOUNT_JSON"])
    else:
        with open(KEY_FILE) as f:
            service_account_info = json.load(f)

    credentials = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES,
    )
    ee.Initialize(credentials, project="gee-chatbot1")

# initialize EE
init_earth_engine()

# -------- OpenAI client (optional) --------
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)
else:
    client = None

# -------- Pydantic models --------
class CompareRequest(BaseModel):
    year_a: int
    year_b: int
    location: Optional[str] = None

class ChatRequest(BaseModel):
    message: Optional[str] = None
    location: Optional[str] = None
    year_a: Optional[int] = None
    year_b: Optional[int] = None
    analysis_function: Optional[str] = None

# -------- helpers --------
def parse_location_to_bbox(location_str):
    """
    Accepts:
      - "minLon,minLat,maxLon,maxLat" -> returns [minLon,minLat,maxLon,maxLat]
      - "lat,lon" or "lon,lat" -> returns small bbox around center
      - otherwise -> returns None (server will use default AOI)
    """
    if not location_str:
        return None
    parts = [p.strip() for p in location_str.split(",") if p.strip() != ""]
    try:
        if len(parts) == 4:
            nums = [float(x) for x in parts]
            return nums
        if len(parts) == 2:
            a = float(parts[0]); b = float(parts[1])
            # detect lat,lon by range
            if -90 <= a <= 90 and -180 <= b <= 180:
                lat = a; lon = b
            else:
                lon = a; lat = b
            delta = 0.05
            return [lon - delta, lat - delta, lon + delta, lat + delta]
    except Exception:
        return None
    return None

# -------- endpoints --------
@app.get("/")
def root():
    return {"status": "ok", "message": "GEE chatbot backend running"}

@app.post("/compare_abudhabi_dw")
def compare_abudhabi_dw(req: CompareRequest):
    roi_bounds = None
    if req.location:
        roi_bounds = parse_location_to_bbox(req.location)
    data = compare_dw_abudhabi_years(req.year_a, req.year_b, roi_bounds=roi_bounds)
    text = f"Dynamic World comparison between {data['year_a']} and {data['year_b']}."
    return {"message": text, "data": data}

@app.post("/chat")
def chat(req: ChatRequest):
    # If UI supplied years, run comparison directly (no OpenAI needed)
    if req.year_a is not None and req.year_b is not None:
        roi_bounds = None
        if req.location:
            roi_bounds = parse_location_to_bbox(req.location)
        data = compare_dw_abudhabi_years(req.year_a, req.year_b, roi_bounds=roi_bounds)
        explanation = f"Dynamic World comparison between {data['year_a']} and {data['year_b']}."
        return {"message": explanation, "data": data}

    # Otherwise fallback to chat via OpenAI (if configured)
    user_message = req.message or ""
    if not client:
        return {
            "message": "OpenAI not configured. Provide OPENAI_API_KEY to enable chat.",
            "data": None,
        }

    # Tools for function calling (optional)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "compare_dw_abudhabi_years",
                "description": "Compare Dynamic World between two years for a specified bounding box.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "year_a": {"type": "integer"},
                        "year_b": {"type": "integer"},
                        "roi_bounds": {
                            "type": "array",
                            "items": {"type": "number"},
                        }
                    },
                    "required": ["year_a", "year_b"]
                }
            }
        }
    ]

    completion = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "You are a helpful GIS assistant. Use tools when needed."},
            {"role": "user", "content": user_message},
        ],
        tools=tools,
    )

    message = completion.choices[0].message

    if message.tool_calls:
        tool_call = message.tool_calls[0]
        fn_name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)

        if fn_name == "compare_dw_abudhabi_years":
            year_a = args["year_a"]
            year_b = args["year_b"]
            roi_bounds = args.get("roi_bounds")
            data = compare_dw_abudhabi_years(year_a, year_b, roi_bounds=roi_bounds)
            explanation = f"Dynamic World comparison between {data['year_a']} and {data['year_b']}."
            return {"message": explanation, "data": data}

    return {"message": message.content if hasattr(message, "content") else str(message), "data": None}
