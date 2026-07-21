import datetime
from fastapi import APIRouter, HTTPException, Depends
from app.db import collection, history_collection
from app.core.security import verify_admin_permission

router = APIRouter()

@router.post("/logs/archive-and-clear", summary="[Admin] Move Current Logs to History & Clear Live Stream")
async def archive_and_clear_logs(is_admin: bool = Depends(verify_admin_permission)):
    records = await collection.find({}, {"_id": 0}).to_list(length=100000)

    if not records:
        return {"status": "success", "message": "Live log collection is already empty. No action required."}

    archive_batch_id = datetime.datetime.now().strftime("archive_%Y%m%d_%H%M%S")

    for doc in records:
        doc["archivedAt"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        doc["archiveBatchId"] = archive_batch_id

    # 1. Copy into history collection
    await history_collection.insert_many(records)

    # 2. Clear active collection
    delete_result = await collection.delete_many({})

    return {
        "status": "success",
        "archivedCount": delete_result.deleted_count,
        "archiveBatchId": archive_batch_id,
        "message": f"Successfully archived {delete_result.deleted_count} logs to history and cleared active log stream."
    }

@router.get("/logs/history", summary="View Archived History Log Index")
async def get_log_history():
    cursor = history_collection.find({}, {"_id": 0}).sort("archivedAt", -1)
    records = await cursor.to_list(length=1000)
    return {"totalArchived": len(records), "records": records}