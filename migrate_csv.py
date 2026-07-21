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
    skipped_count = 0

    with open(CSV_PATH, mode="r", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)  # Skip header
        
        for row in reader:
            if not row or len(row) < 6:
                continue

            document = {
                "capturedAt": row[0] if len(row) > 0 else "",
                "profileName": row[1] if len(row) > 1 else "Unknown Profile",
                "profileUrl": row[2] if len(row) > 2 else "",
                "postUrl": row[3] if len(row) > 3 else "",
                "privacyType": row[4] if len(row) > 4 else "Unknown",
                "postDatetime": row[5] if len(row) > 5 else "",
                "imageUrl": row[6] if len(row) > 6 else "",
                "status": row[7] if len(row) > 7 else "low_confidence"
            }

            existing = await collection.find_one({
                "postUrl": document["postUrl"],
                "capturedAt": document["capturedAt"]
            })

            if not existing:
                await collection.insert_one(document)
                migrated_count += 1
            else:
                skipped_count += 1

    print(f"✅ Migration complete!")
    print(f"   • Migrated: {migrated_count} records")
    print(f"   • Skipped (Duplicates): {skipped_count} records")

if __name__ == "__main__":
    asyncio.run(migrate())