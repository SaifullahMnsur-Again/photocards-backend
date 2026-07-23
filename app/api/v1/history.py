from fastapi import APIRouter, HTTPException, Depends
from pymongo import UpdateOne
from app.db import collection, history_collection
from app.core.security import verify_admin_permission

router = APIRouter()

@router.post("/logs/archive-and-clear", summary="[Admin] Archive Active Logs and Clear Stream")
async def archive_and_clear_logs(is_admin: bool = Depends(verify_admin_permission)):
    try:
        # 1. Fetch all active stream documents
        active_docs = await collection.find({}, {"_id": 0}).to_list(length=100000)
        
        if not active_docs:
            return {
                "status": "success",
                "message": "Active stream logs are already empty. Nothing to archive.",
                "archived_count": 0
            }

        # 2. Prepare bulk upsert operations based on postUrl
        bulk_operations = []
        for doc in active_docs:
            post_url = doc.get("postUrl")
            if not post_url:
                continue
            
            bulk_operations.append(
                UpdateOne(
                    {"postUrl": post_url},
                    {"$set": doc},
                    upsert=True
                )
            )

        # 3. Execute bulk write to history_collection
        archived_count = 0
        if bulk_operations:
            bulk_res = await history_collection.bulk_write(bulk_operations, ordered=False)
            archived_count = bulk_res.upserted_count + bulk_res.modified_count

        # 4. Clear active collection
        delete_res = await collection.delete_many({})

        return {
            "status": "success",
            "message": f"Successfully archived {len(active_docs)} logs to history database and cleared active stream.",
            "archived_count": len(active_docs),
            "cleared_active_count": delete_res.deleted_count
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Archiving failed: {str(e)}"
        )