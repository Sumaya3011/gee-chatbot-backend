import ee
import json
from google.oauth2 import service_account

print("Starting...")

# 1) Name of your JSON key file
KEY_FILE = "gee-chatbot1-1161b98512d2.json"  # <-- change to your real file name

# 2) Scopes: what this service account is allowed to access
SCOPES = [
    "https://www.googleapis.com/auth/earthengine",
    "https://www.googleapis.com/auth/devstorage.read_write",
]

# 3) Read the key file
with open(KEY_FILE) as f:
    service_account_info = json.load(f)

# 4) Build credentials WITH scopes
credentials = service_account.Credentials.from_service_account_info(
    service_account_info,
    scopes=SCOPES,
)

# 5) Initialize Earth Engine
#    (you can add project='gee-chatbot1' if you want)
ee.Initialize(credentials)

print("Initialized EE successfully")

# 6) Simple test call
info = ee.Number(5).getInfo()
print("Test value:", info)

print("SUCCESS")
