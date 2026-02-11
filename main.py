# main.py
import os
import json
from openai import OpenAI

import ee
from fastapi import FastAPI
from pydantic import BaseModel
from google.oauth2 import service_account

from gee_functions import compare_dw_abudhabi_years

from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles


client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


# -------- Earth Engine initialization --------

# Scopes we need
SCOPES = [
    "https://www.googleapis.com/auth/earthengine",
    "https://www.googleapis.com/auth/devstorage.read_write",
]

# Try to read credentials from ENV (for Render) or from local file
KEY_FILE = "gee-chatbot1-1161b98512d2.json"  # <-- change name to your real key file

if "GEE_SERVICE_ACCOUNT_JSON" in os.environ:
    # For Render / cloud
    service_account_info = json.loads(os.environ["GEE_SERVICE_ACCOUNT_JSON"])
else:
    # For local testing with file
    with open(KEY_FILE) as f:
        service_account_info = json.load(f)

credentials = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=SCOPES,
)

# Initialize Earth Engine
ee.Initialize(credentials, project="gee-chatbot1")

# -------- FastAPI app --------

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # allow all websites (fine for dev)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve frontend (index.html) at /app
app.mount(
    "/app",
    StaticFiles(directory="frontend", html=True),
    name="frontend",
)

class CompareRequest(BaseModel):
    year_a: int
    year_b: int


@app.get("/")
def root():
    return {"status": "ok", "message": "GEE backend is running"}


@app.post("/compare_abudhabi_dw")
def compare_abudhabi_dw(req: CompareRequest):
    """
    Example request body:
    {
      "year_a": 2020,
      "year_b": 2024
    }
    """
    data = compare_dw_abudhabi_years(req.year_a, req.year_b)
    # Simple text summary you can show in your chatbot later
    text = (
        f"Here is the Dynamic World comparison for Abu Dhabi between "
        f"{data['year_a']} and {data['year_b']}."
    )

    return {
        "message": text,
        "data": data,
    }

class ChatRequest(BaseModel):
    message: str


@app.post("/chat")
def chat(req: ChatRequest):

    user_message = req.message

    # Define tools available to the model
    tools = [
        {
            "type": "function",
            "function": {
                "name": "compare_dw_abudhabi_years",
                "description": "Compare Dynamic World land cover between two years for Abu Dhabi city block.",
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
                        }
                    },
                    "required": ["year_a", "year_b"]
                }
            }
        }
    ]

    # Call OpenAI
    completion = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "You are a GIS assistant. Use tools when needed."},
            {"role": "user", "content": user_message}
        ],
        tools=tools
    )

    message = completion.choices[0].message

    # If the model decides to call a function
    if message.tool_calls:
        tool_call = message.tool_calls[0]
        function_name = tool_call.function.name
        arguments = json.loads(tool_call.function.arguments)

        if function_name == "compare_dw_abudhabi_years":
            result = compare_dw_abudhabi_years(
                arguments["year_a"],
                arguments["year_b"]
            )

            explanation = (
                f"Here is the Dynamic World comparison for Abu Dhabi "
                f"between {result['year_a']} and {result['year_b']}."
            )

            return {
                "message": explanation,
                "data": result
            }

    # If no tool call, just return model text
    return {
        "message": message.content,
        "data": None
    }
