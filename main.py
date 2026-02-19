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

# Allow browser calls from anywhere (simpler for now)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend folder at /app
app.mount(
    "/app",
    StaticFiles(directory="frontend", html=True),
    name="frontend",
)

# -------- Earth Engine initialization --------

SCOPES = [
    "https://www.googleapis.com/auth/earthengine",
    "https://www.googleapis.com/auth/devstorage.read_write",
]

# If running on Render, use env var; locally, use a key file
KEY_FILE = "gee-backend-key.json"  # for local dev ONLY (do NOT commit this file)


def init_earth_engine():
    if "GEE_SERVICE_ACCOUNT_JSON" in os.environ:
        service_account_info = json.loads(os.environ["GEE_SERVICE_ACCOUNT_JSON"])
    else:
        # local testing with file; this file is ignored by .gitignore
        with open(KEY_FILE) as f:
            service_account_info = json.load(f)

    credentials = service_account.Credentials.from_service_account_info(
        service_account_info,
        scopes=SCOPES,
    )

    # change project if your GEE project is named differently
    ee.Initialize(credentials, project="gee-chatbot1")


# Initialize EE on startup
init_earth_engine()

# -------- OpenAI client --------

# On Render, set OPENAI_API_KEY in Environment Variables
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
if OPENAI_API_KEY:
    client = OpenAI(api_key=OPENAI_API_KEY)
else:
    client = None  # allow requests that don't use OpenAI


# -------- Pydantic models --------

class CompareRequest(BaseModel):
    year_a: int
    year_b: int
    location: Optional[str] = None  # optional bbox string or name


class ChatRequest(BaseModel):
    message: Optional[str] = None
    location: Optional[str] = None
    year_a: Optional[int] = None
    year_b: Optional[int] = None
    analysis_function: Optional[str] = None


# -------- Endpoints --------

@app.get("/")
def root():
    return {"status": "ok", "message": "GEE chatbot backend running"}


@app.post("/compare_abudhabi_dw")
def compare_abudhabi_dw(req: CompareRequest):
    """
    Simple compare endpoint (explicit). location may be:
      - None -> use default Abu Dhabi AOI
      - "minLon,minLat,maxLon,maxLat" -> will use that bbox
    """
    roi_bounds = None
    if req.location:
        # try parse bbox
        try:
            parts = [p.strip() for p in req.location.split(",")]
            if len(parts) == 4:
                roi_bounds = [float(x) for x in parts]
        except Exception:
            roi_bounds = None

    data = compare_dw_abudhabi_years(req.year_a, req.year_b, roi_bounds=roi_bounds)
    text = (
        f"Here is the Dynamic World comparison for the requested area "
        f"between {data['year_a']} and {data['year_b']}."
    )
    return {
        "message": text,
        "data": data,
    }


@app.post("/chat")
def chat(req: ChatRequest):
    """
    Chat endpoint that supports two flows:
      1) If year_a and year_b are present (or analysis_function), run compare_dw_abudhabi_years directly.
      2) Otherwise, forward the free-text message to OpenAI and optionally handle function calls.
    """

    # If UI supplied years (Run button), call the comparison directly
    if req.year_a is not None and req.year_b is not None:
        # parse location bounding box if provided in the simple bbox format
        roi_bounds = None
        if req.location:
            try:
                parts = [p.strip() for p in req.location.split(",")]
                if len(parts) == 4:
                    roi_bounds = [float(x) for x in parts]
            except Exception:
                roi_bounds = None

        data = compare_dw_abudhabi_years(req.year_a, req.year_b, roi_bounds=roi_bounds)
        explanation = (
            f"Here is the Dynamic World comparison for the requested area "
            f"between {data['year_a']} and {data['year_b']}."
        )
        return {"message": explanation, "data": data}

    # If no years are supplied — fall back to chat / OpenAI behavior
    user_message = req.message or ""
    if not client:
        # OpenAI API not configured — return a helpful error
        return {
            "message": "OpenAI client is not configured on the server. "
                       "Provide OPENAI_API_KEY to enable conversational responses.",
            "data": None,
        }

    # Tools definition for function calling (optional)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "compare_dw_abudhabi_years",
                "description": "Compare Dynamic World land cover between two years for a specified area.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "year_a": {
                            "type": "integer",
                            "description": "First year between 2020 and 2024"
                        },
                        "year_b": {
                            "type": "integer",
                            "description": "Second year between 2020 and 2024"
                        },
                        "roi_bounds": {
                            "type": "array",
                            "items": {"type": "number"},
                            "description": "Optional bounding box [minLon, minLat, maxLon, maxLat]"
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

    # If the model decides to call a function/tool
    if message.tool_calls:
        tool_call = message.tool_calls[0]
        fn_name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)

        if fn_name == "compare_dw_abudhabi_years":
            year_a = args["year_a"]
            year_b = args["year_b"]
            roi_bounds = args.get("roi_bounds")

            data = compare_dw_abudhabi_years(year_a, year_b, roi_bounds=roi_bounds)

            explanation = (
                f"Here is the Dynamic World comparison for the requested area "
                f"between {data['year_a']} and {data['year_b']}."
            )

            return {
                "message": explanation,
                "data": data,
            }

    # If no tool call, just return the model text answer
    return {
        "message": message.content if hasattr(message, "content") else str(message),
        "data": None,
    }
