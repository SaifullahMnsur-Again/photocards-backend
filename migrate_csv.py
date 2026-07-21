import csv
import os
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

from app.config import MONGO_URI, BASE_DIR

CSV_PATH = os.path.join(BASE_DIR, "collected_posts.csv")

async def migrate():
    if not os.path.isfile(CSV_PATH):
        print(f"⚠️ No legacy CSV file found at: {CSV_PATH}")
        return

    print(f"🔄 Connecting to MongoDB at {MONGO_URI}...")
    client = AsyncIOMotorClient(MONGO_URI)
    db = client["photocards_db"]
    collection = db["posts"]

    migrated_count = 0
    updated_count = 0

    with open(CSV_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader, None)  # Skip header
        
        for row in reader:
            if not row or len(row) < 4:
                continue

            post_url = row[3]
            captured_at = row[0] if len(row) > 0 else ""

            existing = await collection.find_one({"postUrl": post_url})

            if not existing:
                doc = {
                    "firstCapturedAt": captured_at,
                    "lastCapturedAt": captured_at,
                    "requestCount": 1,
                    "profileName": row[1] if len(row) > 1 else "Unknown Profile",
                    "profileUrl": row[2] if len(row) > 2 else "",
                    "postUrl": post_url,
                    "privacyType": row[4] if len(row) > 4 else "Unknown",
                    "postDatetime": row[5] if len(row) > 5 else "",
                    "imageUrl": row[6] if len(row) > 6 else "",
                    "status": row[7] if len(row) > 7 else "low_confidence"
                }
                await collection.insert_one(doc)
                migrated_count += 1
            else:
                # Increment count for duplicate legacy records
                await collection.update_one(
                    {"_id": existing["_id"]},
                    {"$inc": {"requestCount": 1}}
                )
                updated_count += 1

    print(f"✅ Migration complete! Inserted {migrated_count} new, updated {updated_count} existing records.")

if __name__ == "__main__":
    asyncio.run(migrate())