#!/usr/bin/env python
"""
scripts/setup_firestore.py
────────────────────────────────────────────────────────────
One-shot bootstrap script for ItemRadarAI:

• Creates Firestore sample docs & collections
• Generates security rules       → firestore.rules
• Prints required composite indexes (gcloud commands)
• Writes Cloud Functions stub    → cloud_functions.js
• Creates / configures a Storage bucket (optional)

Run:
    source .venv/bin/activate
    python scripts/setup_firestore.py --project YOUR_GCP_PROJECT \
                                      --bucket  YOUR_BUCKET_NAME \
                                      --sa      path/to/service-account.json
"""

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import List

from google.cloud import firestore, storage

# ──────────────────────────────────────────────────────────
#  Utils
# ──────────────────────────────────────────────────────────


def banner(msg: str) -> None:
    print(f"\n\033[96m⚙️  {msg}\033[0m")


def green(msg: str) -> None:
    print(f"\033[92m✅ {msg}\033[0m")


def red(msg: str) -> None:
    print(f"\033[91m❌ {msg}\033[0m", file=sys.stderr)


# ──────────────────────────────────────────────────────────
#  Firestore Setup Class
# ──────────────────────────────────────────────────────────


class FirestoreSetup:
    """One-shot bootstrapper for ItemRadarAI Firestore"""

    # ── constructor ───────────────────────────────────────
    def __init__(self, project_id: str, credentials: str | None):
        self.project_id = project_id
        if credentials:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials

        self.db = firestore.Client(project=project_id)
        self.storage_client = storage.Client(project=project_id)

    # ── main entrypoint ───────────────────────────────────
    def run_full_setup(self, bucket_name: str | None = None) -> None:
        banner("Starting ItemRadarAI Firestore bootstrap")
        print(f"📋 Project ID: {self.project_id}")

        self.create_collections()
        if bucket_name:
            self.setup_storage_bucket(bucket_name)
        self.generate_security_rules()
        self.print_indexes()
        self.write_cloud_functions_stub()

        banner("🎉 All done! Next steps")
        print(
            """\
1. Deploy security rules:
      firebase deploy --only firestore:rules

2. Create indexes (copy & paste printed gcloud commands).

3. Deploy cloud functions (after editing cloud_functions.js):
      firebase deploy --only functions

4. Verify collections and bucket in Firebase Console."""
        )

    # ──────────────────────────────────────────────────
    # 1. Create sample documents
    # ──────────────────────────────────────────────────
    def create_collections(self) -> None:
        banner("Creating initial collections & sample documents")

        # 1) foundItems
        found_sample = {
            "item_id": "sample_found_001",
            "description": "🎒 Sample red backpack for testing",
            "embedding": [0.0] * 128,  # placeholder
            "photos": ["gs://sample/path.jpg"],
            "location": {
                "lat": 40.7128,
                "lng": -74.0060,
                "address": "Central Park, NYC",
                "geo_hash": "dr5regy",
            },
            "timestamp": firestore.SERVER_TIMESTAMP,
            "finder": {
                "user_id": "uid_test",
                "contact_method": "email",
                "contact_value": "finder@example.com",
            },
            "status": "available",
            "category": "bag",
            "ai_generated": {"keywords": ["red", "backpack"], "confidence": 0.9},
            "expiry_date": firestore.SERVER_TIMESTAMP,
        }
        self.db.collection("foundItems").document("sample_found_001").set(found_sample)
        green("foundItems → sample doc created")

        # 2) users
        user_sample = {
            "user_id": "uid_test",
            "contact_preferences": {
                "email": "finder@example.com",
                "whatsapp": "+1234567890",
                "notifications_enabled": True,
            },
            "created_at": firestore.SERVER_TIMESTAMP,
            "last_active": firestore.SERVER_TIMESTAMP,
        }
        self.db.collection("users").document("uid_test").set(user_sample)
        green("users → sample doc created")

        # 3) analytics
        analytic_sample = {
            "event": "found_item_created",
            "timestamp": firestore.SERVER_TIMESTAMP,
            "location": {
                "lat": 40.7128,
                "lng": -74.0060,
                "address": "Central Park, NYC",
            },
            "category": "bag",
        }
        self.db.collection("analytics").document("sample_evt").set(analytic_sample)
        green("analytics → sample doc created")

    # ──────────────────────────────────────────────────
    # 2. Storage bucket
    # ──────────────────────────────────────────────────
    def setup_storage_bucket(self, bucket_name: str) -> None:
        banner(f"Ensuring storage bucket '{bucket_name}' exists")
        bucket = self.storage_client.bucket(bucket_name)
        if not bucket.exists():
            bucket = self.storage_client.create_bucket(
                bucket_name, location="us-central1"
            )
            green(f"Bucket {bucket_name} created")
        else:
            green(f"Bucket {bucket_name} already exists")

        # Set simple CORS
        bucket.cors = [
            {
                "origin": ["*"],
                "method": ["GET", "POST", "PUT"],
                "responseHeader": ["Content-Type"],
                "maxAgeSeconds": 3600,
            }
        ]
        bucket.patch()
        green("CORS configuration applied")

    # ──────────────────────────────────────────────────
    # 3. Security rules
    # ──────────────────────────────────────────────────
    def generate_security_rules(self) -> None:
        banner("Writing firestore.rules")
        rules = f"""rules_version = '2';
service cloud.firestore {{
  match /databases/{{database}}/documents {{

    // Found items
    match /foundItems/{{itemId}} {{
      allow read: if true;  // public search
      allow create: if request.auth != null
        && request.auth.uid == request.resource.data.finder.user_id;
      allow update, delete: if request.auth != null
        && request.auth.uid == resource.data.finder.user_id;
    }}

    // Users
    match /users/{{userId}} {{
      allow read, write: if request.auth != null && request.auth.uid == userId;
    }}

    // Analytics – read-only to authed users
    match /analytics/{{doc=**}} {{
      allow read: if request.auth != null;
      allow write: if false;
    }}
  }}
}}"""
        Path("firestore.rules").write_text(rules, encoding="utf-8")
        green("firestore.rules written")

    # ──────────────────────────────────────────────────
    # 4. Index list
    # ──────────────────────────────────────────────────
    def print_indexes(self) -> None:
        banner("Composite indexes you MUST create")

        indexes: List[dict] = [
            {
                "collection": "foundItems",
                "fields": [("status", "ASCENDING"), ("timestamp", "DESCENDING")],
            },
            {
                "collection": "foundItems",
                "fields": [
                    ("category", "ASCENDING"),
                    ("status", "ASCENDING"),
                    ("timestamp", "DESCENDING"),
                ],
            },
            {
                "collection": "foundItems",
                "fields": [
                    ("location.lat", "ASCENDING"),
                    ("status", "ASCENDING"),
                ],
            },
            {
                "collection": "analytics",
                "fields": [
                    ("event", "ASCENDING"),
                    ("timestamp", "DESCENDING"),
                ],
            },
        ]

        for idx in indexes:
            parts = " \\\n  ".join(
                f"--field-config field-path={path},order={order}"
                for path, order in idx["fields"]
            )
            cmd = (
                "gcloud firestore indexes composite create \\\n"
                f"  --collection-group={idx['collection']} \\\n  {parts}"
            )
            print(cmd, "\n")

    # ──────────────────────────────────────────────────
    # 5. Cloud Functions stub
    # ──────────────────────────────────────────────────
    def write_cloud_functions_stub(self) -> None:
        banner("Writing cloud_functions.js stub")
        stub_code = """\
// Cloud Functions stub for ItemRadarAI
// After editing, deploy with: firebase deploy --only functions

const functions = require('firebase-functions');
const admin     = require('firebase-admin');
admin.initializeApp();
const db = admin.firestore();

// Trigger: new found item
exports.onFoundItemCreated = functions.firestore
  .document('foundItems/{itemId}')
  .onCreate(async (snap, context) => {
    const data = snap.data();
    console.log('New found item:', context.params.itemId);
    // TODO: call matching engine / PubSub
  });

// Scheduled cleanup
exports.cleanupExpired = functions.pubsub
  .schedule('0 2 * * *').onRun(async () => {
    const now = admin.firestore.Timestamp.now();
    const snapshot = await db.collection('foundItems')
      .where('expiry_date', '<', now)
      .where('status', '==', 'available').get();
    const batch = db.batch();
    snapshot.forEach(doc => batch.update(doc.ref, { status: 'expired' }));
    await batch.commit();
    console.log(`Expired ${snapshot.size} items`);
  });
"""
        Path("cloud_functions.js").write_text(stub_code, encoding="utf-8")
        green("cloud_functions.js written")


# ──────────────────────────────────────────────────────────
#  Main CLI
# ──────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(description="ItemRadarAI Firestore bootstrap")
    parser.add_argument("--project", required=True, help="GCP project id")
    parser.add_argument(
        "--sa",
        dest="service_account",
        help="Path to service-account JSON (optional if ADC already configured)",
    )
    parser.add_argument(
        "--bucket",
        help="Create / configure this Cloud Storage bucket (optional)",
    )
    args = parser.parse_args()

    setup = FirestoreSetup(args.project, args.service_account)
    setup.run_full_setup(args.bucket)


if __name__ == "__main__":
    main()
