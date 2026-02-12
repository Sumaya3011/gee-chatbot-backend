# main.py
import os
import json

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
client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


# -------- Pydantic models --------

class CompareRequest(BaseModel):
    year_a: int
    year_b: int


class ChatRequest(BaseModel):
    message: str


# -------- Endpoints --------

@app.get("/")
def root():
    return {"status": "ok", "message": "GEE chatbot backend running"}


@app.post("/compare_abudhabi_dw")
def compare_abudhabi_dw(req: CompareRequest):
    data = compare_dw_abudhabi_years(req.year_a, req.year_b)
    text = (
        f"Here is the Dynamic World comparison for Abu Dhabi between "
        f"{data['year_a']} and {data['year_b']}."
    )
    return {
        "message": text,
        "data": data,
    }


@app.post("/chat")
def chat(req: ChatRequest):
    user_message = req.message

    # Tools definition for function calling
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

            data = compare_dw_abudhabi_years(year_a, year_b)

            explanation = (
                f"Here is the Dynamic World comparison for Abu Dhabi between "
                f"{data['year_a']} and {data['year_b']}."
            )

            return {
                "message": explanation,
                "data": data,
            }

    # If no tool call, just return the model text answer
    return {
        "message": message.content,
        "data": None,
    }
