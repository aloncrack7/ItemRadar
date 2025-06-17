# upload_handbags.py

import os
import datetime
from dotenv import load_dotenv
from google.cloud import firestore

# ─── Bootstrap ────────────────────────────────────────────────────
load_dotenv()  # expects PROJECT_ID and GOOGLE_APPLICATION_CREDENTIALS in your .env
PROJECT_ID = os.getenv("PROJECT_ID")
if not PROJECT_ID:
    raise RuntimeError("PROJECT_ID must be set in your .env")

# Initialize Firestore client
db = firestore.Client(project=PROJECT_ID)

# ─── Define your batch of handbags ────────────────────────────────
# Feel free to add/remove or tweak these entries:
items = [
    {
        "id":          "handbag_001",
        "description": "Black leather tote with gold hardware and removable tassel",
        "address":     "Puerta de Alcalá, Madrid, Spain",
        "lat":         40.4199835,
        "lon":        -3.6887262,
        "email":       "alice@example.com",
        "status":      "active",
        "timestamp":   datetime.datetime(2025, 6, 15, 16, 53, 13, tzinfo=datetime.timezone(datetime.timedelta(hours=-5)))
    },
    {
        "id":          "handbag_002",
        "description": "Brown suede satchel with adjustable strap and embossed logo",
        "address":     "Gran Vía, Madrid, Spain",
        "lat":         40.4202928,
        "lon":        -3.7056479,
        "email":       "bob@example.com",
        "status":      "active",
        "timestamp":   datetime.datetime(2025, 6, 15, 17,  5, 30, tzinfo=datetime.timezone(datetime.timedelta(hours=-5)))
    },
    {
        "id":          "handbag_003",
        "description": "Red canvas crossbody bag with silver zipper and front pocket",
        "address":     "Calle de Alcalá, Madrid, Spain",
        "lat":         40.4187041,
        "lon":        -3.6951157,
        "email":       "carol@example.com",
        "status":      "active",
        "timestamp":   datetime.datetime(2025, 6, 15, 17, 27, 45, tzinfo=datetime.timezone(datetime.timedelta(hours=-5)))
    },
    # …add as many variations as you need…
]

def upload_items(batch):
    for item in batch:
        doc_ref = db.collection("found_items").document(item["id"])
        # Prepare Firestore‐friendly dict
        payload = {
            "id":          item["id"],
            "description": item["description"],
            "address":     item["address"],
            "lat":         item["lat"],
            "lon":         item["lon"],
            "email":       item["email"],
            "status":      item["status"],
            "timestamp":   item["timestamp"],
        }
        print(f"Uploading {item['id']}…", end=" ")
        doc_ref.set(payload)
        print("✅ done")

if __name__ == "__main__":
    print("=== Batch Uploading Handbags to Firestore ===")
    upload_items(items)
    print("All items uploaded.")
