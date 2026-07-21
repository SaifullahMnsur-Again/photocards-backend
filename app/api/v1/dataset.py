import os
import io
import csv
import zipfile
import shutil
import datetime
from typing import Optional, Literal, Dict, Any, List
from fastapi import APIRouter, HTTPException, Query, Depends, Form
from fastapi.responses import StreamingResponse

from app.config import IMAGE_DIR, SERVER_DOMAIN
from app.db import collection, dataset_collection
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


# --- 1. DATASET EXPORT (JSON / CSV) ---
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


# --- 2. CREATE ISOLATED WORKING DATASET COPY ---
@router.post("/dataset/create-working-copy", summary="[Admin] Create Isolated Dataset Copy")
async def create_working_dataset_copy(
    copy_name: str = Query("dataset_v1", description="Name for working copy batch"),
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
    records = await collection.find(query, {"_id": 0}).to_list(length=100000)

    if not records:
        raise HTTPException(status_code=404, detail="No source records found matching specified filters.")

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for doc in records:
        doc["datasetCopyName"] = copy_name
        doc["copiedAt"] = timestamp
        doc["isVerifiedLabel"] = False

    await dataset_collection.insert_many(records)

    return {
        "status": "success",
        "copyName": copy_name,
        "copiedCount": len(records),
        "message": f"Successfully created working dataset copy '{copy_name}' with {len(records)} records."
    }


# --- 3. UPDATE LABEL IN WORKING DATASET ---
@router.patch("/dataset/update-item-label", summary="[Admin] Modify Class Label in Dataset Copy")
async def update_item_label(
    postUrl: str = Form(...),
    new_status: str = Form(...),
    is_admin: bool = Depends(verify_admin_permission)
):
    result = await dataset_collection.update_many(
        {"postUrl": postUrl},
        {"$set": {"status": new_status, "isVerifiedLabel": True}}
    )

    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found in working dataset copy.")

    return {"status": "success", "updatedCount": result.modified_count, "newStatus": new_status}


# --- 4. BATCH RENAME WORKING DATASET IMAGES ---
@router.post("/dataset/batch-rename", summary="[Admin] Batch Rename Working Dataset Images")
async def batch_rename_dataset_images(
    prefix: str = Query("photocard_batch", description="Image prefix"),
    is_admin: bool = Depends(verify_admin_permission)
):
    cursor = dataset_collection.find({"imageUrl": {"$ne": ""}}).sort("copiedAt", 1)
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

            await dataset_collection.update_one(
                {"_id": record["_id"]},
                {"$set": {"imageUrl": new_url, "batchPrefix": prefix}}
            )
            renamed_count += 1

    return {"status": "success", "renamedCount": renamed_count, "prefix": prefix}


# --- 5. EXPORT WORKING DATASET AS CLASSIFICATION ZIP ---
@router.get("/dataset/generate-classification-zip", summary="[Admin] Export Working Dataset ZIP")
async def generate_classification_dataset_zip(
    is_admin: bool = Depends(verify_admin_permission)
):
    records = await dataset_collection.find({}, {"_id": 0}).to_list(length=100000)

    if not records:
        raise HTTPException(status_code=404, detail="Working dataset copy is empty. Create a working copy first.")

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
        headers={"Content-Disposition": f"attachment; filename=working_dataset_{timestamp_str}.zip"}
    )