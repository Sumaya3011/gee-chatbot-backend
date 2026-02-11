# main.py
import os
import json

import ee
from fastapi import FastAPI
from pydantic import BaseModel
from google.oauth2 import service_account

from gee_functions import compare_dw_abudhabi_years

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
