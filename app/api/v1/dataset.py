import os
import io
import csv
import json
import zipfile
import shutil
import datetime
from typing import Optional, Literal, Dict, Any, List
from fastapi import APIRouter, HTTPException, Query, Depends, Form
from fastapi.responses import StreamingResponse

from app.config import IMAGE_DIR, SERVER_DOMAIN
from app.db import collection, dataset_collection, projects_collection
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
            query.setdefault("firstCapturedAt", {})["$gte"] = f"{val} 00:00:00"
        elif param == "end_date":
            query.setdefault("firstCapturedAt", {})["$lte"] = f"{val} 23:59:59"

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
    cursor = collection.find(query, {"_id": 0}).sort("firstCapturedAt", -1)
    records = await cursor.to_list(length=100000)

    if not records:
        raise HTTPException(status_code=404, detail="No dataset records match the specified query.")

    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if format == "json":
        json_bytes = json.dumps(records, indent=2, ensure_ascii=False).encode("utf-8")
        return StreamingResponse(
            io.BytesIO(json_bytes),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=photocard_dataset_{timestamp_str}.json"}
        )

    output = io.StringIO()
    writer = csv.DictWriter(
        output, 
        fieldnames=["firstCapturedAt", "lastCapturedAt", "requestCount", "profileName", "profileUrl", "postUrl", "privacyType", "postDatetime", "imageUrl", "status"]
    )
    writer.writeheader()
    for row in records:
        writer.writerow({
            "firstCapturedAt": row.get("firstCapturedAt", row.get("capturedAt", "")),
            "lastCapturedAt": row.get("lastCapturedAt", ""),
            "requestCount": row.get("requestCount", 1),
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


# --- 2. CREATE DATASET PROJECT WITH CUSTOM CLASSES ---
@router.post("/projects/create", summary="[Admin] Create New Dataset Project")
async def create_dataset_project(
    project_id: str = Form(..., description="Unique slug identifier (e.g., 'political_ads_v1')"),
    title: str = Form(...),
    classes: str = Form(..., description="Comma-separated class names (e.g., 'hate,neutral,spam')"),
    is_admin: bool = Depends(verify_admin_permission)
):
    existing = await projects_collection.find_one({"projectId": project_id})
    if existing:
        raise HTTPException(status_code=400, detail="Project ID already exists.")

    class_list = [c.strip().lower() for c in classes.split(",") if c.strip()]
    if not class_list:
        raise HTTPException(status_code=400, detail="At least one custom class label must be specified.")

    project_doc = {
        "projectId": project_id,
        "title": title,
        "classes": class_list,
        "createdAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    await projects_collection.insert_one(project_doc)
    return {"status": "success", "project": project_doc}


# --- 3. LIST ALL DATASET PROJECTS ---
@router.get("/projects/list", summary="List All Dataset Projects")
async def list_dataset_projects():
    projects = await projects_collection.find({}, {"_id": 0}).to_list(1000)
    return {"projects": projects}


# --- 4. IMPORT LOGS INTO PROJECT (METADATA & CENTRAL IMAGE LINKS ONLY) ---
@router.post("/projects/import-items", summary="[Admin] Import Items to Project")
async def import_items_to_project(
    project_id: str = Form(...),
    filters_raw: Optional[str] = Form(None),
    is_admin: bool = Depends(verify_admin_permission)
):
    project = await projects_collection.find_one({"projectId": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    default_class = project["classes"][0]
    raw_logs = await collection.find({}, {"_id": 0}).to_list(100000)

    imported_count = 0
    for doc in raw_logs:
        exists = await dataset_collection.find_one({
            "projectId": project_id,
            "postUrl": doc.get("postUrl", "")
        })

        if not exists:
            item_doc = {
                "projectId": project_id,
                "postUrl": doc.get("postUrl", ""),
                "profileName": doc.get("profileName", "Unknown"),
                "profileUrl": doc.get("profileUrl", ""),
                "privacyType": doc.get("privacyType", "Unknown"),
                "postDatetime": doc.get("postDatetime", ""),
                "imageUrl": doc.get("imageUrl", ""),
                "firstCapturedAt": doc.get("firstCapturedAt", doc.get("capturedAt", "")),
                "customClass": default_class,
                "isVerified": False,
                "addedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            await dataset_collection.insert_one(item_doc)
            imported_count += 1

    return {"status": "success", "importedCount": imported_count, "projectId": project_id}


# --- 5. UPDATE ITEM CLASS LABEL IN PROJECT ---
@router.patch("/projects/update-label", summary="[Admin] Update Custom Label")
async def update_item_custom_label(
    project_id: str = Form(...),
    post_url: str = Form(...),
    new_class: str = Form(...),
    is_admin: bool = Depends(verify_admin_permission)
):
    project = await projects_collection.find_one({"projectId": project_id})
    if not project or new_class not in project["classes"]:
        raise HTTPException(status_code=400, detail="Invalid project or custom class label.")

    res = await dataset_collection.update_one(
        {"projectId": project_id, "postUrl": post_url},
        {"$set": {"customClass": new_class, "isVerified": True}}
    )

    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found in project.")

    return {"status": "success", "updatedClass": new_class}


# --- 6. EXPORT PROJECT DATASET ZIP ---
@router.get("/projects/export-zip", summary="[Admin] Export Project ZIP Archive")
async def export_project_zip(
    project_id: str = Query(...),
    is_admin: bool = Depends(verify_admin_permission)
):
    project = await projects_collection.find_one({"projectId": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    items = await dataset_collection.find({"projectId": project_id}, {"_id": 0}).to_list(100000)
    if not items:
        raise HTTPException(status_code=404, detail="Project contains no items.")

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for item in items:
            img_url = item.get("imageUrl", "")
            assigned_class = item.get("customClass", "unlabeled")

            if img_url:
                filename = os.path.basename(img_url)
                disk_path = os.path.join(IMAGE_DIR, filename)

                if os.path.exists(disk_path):
                    zip_path = f"{project_id}/{assigned_class}/{filename}"
                    zip_file.write(disk_path, arcname=zip_path)

        manifest_data = json.dumps({"project": project, "records": items}, indent=2, ensure_ascii=False)
        zip_file.writestr(f"{project_id}/manifest.json", manifest_data)

    zip_buffer.seek(0)
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={project_id}_{timestamp_str}.zip"}
    )