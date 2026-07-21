import os
import io
import csv
import zipfile
import shutil
import datetime
from typing import Optional, Literal, Dict, Any, List
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse

from app.config import IMAGE_DIR, SERVER_DOMAIN
from app.db import collection
from app.core.security import verify_admin_permission

router = APIRouter()

def build_advanced_mongo_query(filters_list: List[Dict[str, str]]) -> Dict[str, Any]:
    query: Dict[str, Any] = {}
    for f in filters_list:
        mode = f.get("mode", "inc")
        param = f.get("param", "")
        val = f.get("val", "").strip()

        if not param or not val:
            continue

        if param == "status":
            query["status"] = val if mode == "inc" else {"$ne": val}
        elif param == "privacyType":
            query["privacyType"] = {"$regex": val, "$options": "i"} if mode == "inc" else {"$not": {"$regex": val, "$options": "i"}}
        elif param in ["profileName", "profileUrl", "postUrl"]:
            query[param] = {"$regex": val, "$options": "i"} if mode == "inc" else {"$not": {"$regex": val, "$options": "i"}}
        elif param == "start_date":
            query.setdefault("capturedAt", {})["$gte"] = f"{val} 00:00:00"
        elif param == "end_date":
            query.setdefault("capturedAt", {})["$lte"] = f"{val} 23:59:59"

    return query


# --- ENDPOINT 1: DATASET EXPORT (JSON / CSV) ---
@router.get("/dataset/download")
async def download_dataset(
    format: Literal["json", "csv"] = Query("json"),
    filters_raw: Optional[str] = Query(None)
):
    filters_list = []
    if filters_raw:
        for chunk in filters_raw.split("|"):
            parts = chunk.split(":")
            if len(parts) == 3:
                filters_list.append({"mode": parts[0], "param": parts[1], "val": parts[2]})

    query = build_advanced_mongo_query(filters_list)
    cursor = collection.find(query, {"_id": 0}).sort("capturedAt", -1)
    records = await cursor.to_list(length=100000)

    if not records:
        raise HTTPException(status_code=404, detail="No dataset records match the specified query.")

    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if format == "json":
        import json
        json_bytes = json.dumps(records, indent=2, ensure_ascii=False).encode("utf-8")
        return StreamingResponse(
            io.BytesIO(json_bytes),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=photocard_dataset_{timestamp_str}.json"}
        )

    output = io.StringIO()
    writer = csv.DictWriter(
        output, 
        fieldnames=["capturedAt", "profileName", "profileUrl", "postUrl", "privacyType", "postDatetime", "imageUrl", "status"]
    )
    writer.writeheader()
    for row in records:
        writer.writerow({
            "capturedAt": row.get("capturedAt", ""),
            "profileName": row.get("profileName", "Unknown Profile"),
            "profileUrl": row.get("profileUrl", ""),
            "postUrl": row.get("postUrl", ""),
            "privacyType": row.get("privacyType", "Unknown"),
            "postDatetime": row.get("postDatetime", ""),
            "imageUrl": row.get("imageUrl", ""),
            "status": row.get("status", "low_confidence")
        })

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=photocard_dataset_{timestamp_str}.csv"}
    )


# --- ENDPOINT 2: ADMIN IMAGE BATCHER & RENAMER ---
@router.post("/dataset/batch-rename", summary="[Admin] Batch Rename Image Assets")
async def batch_rename_images(
    prefix: str = Query("photocard_batch", description="Prefix for renamed images"),
    is_admin: bool = Depends(verify_admin_permission)
):
    cursor = collection.find({"imageUrl": {"$ne": ""}}).sort("capturedAt", 1)
    records = await cursor.to_list(length=100000)

    renamed_count = 0
    for idx, record in enumerate(records, start=1):
        old_url = record.get("imageUrl", "")
        if not old_url:
            continue

        filename = os.path.basename(old_url)
        old_filepath = os.path.join(IMAGE_DIR, filename)

        if os.path.exists(old_filepath):
            ext = os.path.splitext(filename)[1] or ".png"
            new_filename = f"{prefix}_{idx:05d}{ext}"
            new_filepath = os.path.join(IMAGE_DIR, new_filename)

            shutil.move(old_filepath, new_filepath)
            new_url = f"{SERVER_DOMAIN}/media/images/{new_filename}"

            await collection.update_one(
                {"_id": record["_id"]},
                {"$set": {"imageUrl": new_url, "batchName": prefix}}
            )
            renamed_count += 1

    return {
        "status": "success",
        "message": f"Successfully batch-renamed {renamed_count} image assets.",
        "batchPrefix": prefix
    }


# --- ENDPOINT 3: ADMIN CLASSIFICATION DATASET ZIP MAKER ---
@router.get("/dataset/generate-classification-zip", summary="[Admin] Export Classification Dataset ZIP")
async def generate_classification_dataset(
    filters_raw: Optional[str] = Query(None),
    is_admin: bool = Depends(verify_admin_permission)
):
    filters_list = []
    if filters_raw:
        for chunk in filters_raw.split("|"):
            parts = chunk.split(":")
            if len(parts) == 3:
                filters_list.append({"mode": parts[0], "param": parts[1], "val": parts[2]})

    query = build_advanced_mongo_query(filters_list)
    cursor = collection.find(query, {"_id": 0})
    records = await cursor.to_list(length=100000)

    if not records:
        raise HTTPException(status_code=404, detail="No records matched the filter criteria.")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        manifest = []

        for record in records:
            img_url = record.get("imageUrl", "")
            status_cls = record.get("status", "unlabeled")

            if img_url:
                img_name = os.path.basename(img_url)
                img_path_disk = os.path.join(IMAGE_DIR, img_name)

                if os.path.exists(img_path_disk):
                    zip_path = f"dataset/{status_cls}/{img_name}"
                    zip_file.write(img_path_disk, arcname=zip_path)

            manifest.append(record)

        import json
        manifest_bytes = json.dumps(manifest, indent=2, ensure_ascii=False)
        zip_file.writestr("dataset/manifest.json", manifest_bytes)

    zip_buffer.seek(0)
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=classification_dataset_{timestamp_str}.zip"}
    )