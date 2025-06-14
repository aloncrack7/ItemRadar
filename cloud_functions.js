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
