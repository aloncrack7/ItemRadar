/* eslint-disable max-len */

/**
 * Cloud Functions for ItemRadarAI – v2 API
 * Uses:
 *   - Firestore document triggers
 *   - Scheduled Pub/Sub
 *   - HTTPS health-check
 */

const {onDocumentCreated} = require("firebase-functions/v2/firestore");
const {onSchedule} = require("firebase-functions/v2/scheduler");
const {onRequest} = require("firebase-functions/v2/https");
const admin = require("firebase-admin");
const {PubSub} = require("@google-cloud/pubsub");

admin.initializeApp();
const db = admin.firestore();
const pubsub = new PubSub();

// ─────────────────────────────────────────────────────────────
// Trigger: New found item created
// Path:    foundItems/{itemId}
// ─────────────────────────────────────────────────────────────
exports.onFoundItemCreated = onDocumentCreated("foundItems/{itemId}", async (event) => {
  const itemData = event.data.data(); // v2: event.data is the snapshot
  const itemId = event.params.itemId;

  console.log(`New found item created: ${itemId}`);

  // Publish to Pub/Sub for the matcher agent
  await pubsub
      .topic("item-matching")
      .publishMessage({json: {itemId, embedding: itemData.embedding, category: itemData.category}});

  // Write simple analytics doc
  await db.collection("analytics").add({
    event: "found_item_created",
    timestamp: admin.firestore.FieldValue.serverTimestamp(),
    location: itemData.location,
    category: itemData.category,
  });

  return;
});

// ─────────────────────────────────────────────────────────────
// Trigger: Match created
// Path:    matches/{matchId}
// ─────────────────────────────────────────────────────────────
exports.onMatchCreated = onDocumentCreated("matches/{matchId}", async (event) => {
  const matchData = event.data.data();
  console.log("Match created:", matchData.match_id);

  // Example notification placeholder (implement send logic)
  // await sendMatchNotifications(matchData);
  return;
});

// ─────────────────────────────────────────────────────────────
// Scheduled cleanup of expired items (runs daily at 03:00 UTC)
// ─────────────────────────────────────────────────────────────
exports.cleanupExpiredItems = onSchedule("0 3 * * *", async () => {
  const now = admin.firestore.Timestamp.now();

  const expiredSnap = await db
      .collection("foundItems")
      .where("expiry_date", "<", now)
      .where("status", "==", "available")
      .get();

  const batch = db.batch();
  expiredSnap.forEach((doc) => {
    batch.update(doc.ref, {status: "expired"});
  });

  await batch.commit();
  console.log(`Expired ${expiredSnap.size} items`);
});

// ─────────────────────────────────────────────────────────────
// Simple HTTPS health-check
// URL: https://REGION-PROJECT.cloudfunctions.net/healthcheck
// ─────────────────────────────────────────────────────────────
exports.healthcheck = onRequest({region: "us-central1"}, (req, res) => {
  res.status(200).send(`ItemRadarAI Functions are alive! - ${new Date().toISOString()}`);
});
