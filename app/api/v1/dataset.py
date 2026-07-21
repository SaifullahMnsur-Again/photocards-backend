import os
import io
import csv
import json
import zipfile
import datetime
import urllib.parse
from typing import Optional, Literal, Dict, Any, List
import httpx
from fastapi import APIRouter, HTTPException, Query, Depends, Form
from fastapi.responses import StreamingResponse

from app.config import IMAGE_DIR, SERVER_DOMAIN
from app.db import collection, history_collection, dataset_collection, projects_collection
from app.core.security import verify_admin_permission
from app.version import APP_VERSION

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
        raise HTTPException(status_code=404, detail="No dataset records match query.")

    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if format == "json":
        json_bytes = json.dumps({"version": APP_VERSION, "data": records}, indent=2, ensure_ascii=False).encode("utf-8")
        return StreamingResponse(
            io.BytesIO(json_bytes),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=dataset_v{APP_VERSION}_{timestamp_str}.json"}
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
        headers={"Content-Disposition": f"attachment; filename=dataset_v{APP_VERSION}_{timestamp_str}.csv"}
    )


# --- 2. CREATE OR UPSERT DATASET PROJECT ---
@router.post("/projects/create", summary="[Admin] Create New Dataset Project")
async def create_dataset_project(
    project_id: str = Form(...),
    title: str = Form(...),
    classes: str = Form(...),
    overwrite: bool = Form(False),
    is_admin: bool = Depends(verify_admin_permission)
):
    class_list = [c.strip().lower() for c in classes.split(",") if c.strip()]
    if not class_list:
        raise HTTPException(status_code=400, detail="Must specify at least one custom class label.")

    existing = await projects_collection.find_one({"projectId": project_id})
    if existing and not overwrite:
        raise HTTPException(
            status_code=400, 
            detail=f"Project ID '{project_id}' already exists. Select 'Overwrite' to replace."
        )

    project_doc = {
        "projectId": project_id,
        "title": title,
        "classes": class_list,
        "version": APP_VERSION,
        "updatedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    if existing and overwrite:
        await projects_collection.update_one({"projectId": project_id}, {"$set": project_doc})
    else:
        project_doc["createdAt"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        await projects_collection.insert_one(project_doc)

    return {"status": "success", "project": project_doc, "apiVersion": APP_VERSION}


# --- 3. EDIT DATASET PROJECT SETTINGS ---
@router.patch("/projects/update-settings", summary="[Admin] Update Project Settings")
async def update_project_settings(
    project_id: str = Form(...),
    title: Optional[str] = Form(None),
    classes: Optional[str] = Form(None),
    is_admin: bool = Depends(verify_admin_permission)
):
    project = await projects_collection.find_one({"projectId": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    update_doc = {}
    if title:
        update_doc["title"] = title
    if classes:
        class_list = [c.strip().lower() for c in classes.split(",") if c.strip()]
        if class_list:
            update_doc["classes"] = class_list

    if update_doc:
        await projects_collection.update_one({"projectId": project_id}, {"$set": update_doc})

    return {"status": "success", "updated": update_doc}


# --- 4. DELETE ENTIRE DATASET PROJECT ---
@router.delete("/projects/delete", summary="[Admin] Delete Entire Project")
async def delete_dataset_project(
    project_id: str = Query(...),
    is_admin: bool = Depends(verify_admin_permission)
):
    project = await projects_collection.find_one({"projectId": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    await projects_collection.delete_one({"projectId": project_id})
    del_res = await dataset_collection.delete_many({"projectId": project_id})

    return {
        "status": "success",
        "deletedProjectId": project_id,
        "deletedItemsCount": del_res.deleted_count
    }


# --- 5. DELETE SINGLE ITEM FROM PROJECT ---
@router.delete("/projects/delete-item", summary="[Admin] Delete Single Item from Project")
async def delete_project_item(
    project_id: str = Query(...),
    post_url: str = Query(...),
    is_admin: bool = Depends(verify_admin_permission)
):
    res = await dataset_collection.delete_one({"projectId": project_id, "postUrl": post_url})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Item not found in project.")

    return {"status": "success", "deletedPostUrl": post_url}


# --- 6. UNIVERSAL IMPORT ENGINE ---
@router.post("/projects/import-external", summary="[Admin] Universal Import Engine")
async def import_items_universal(
    project_id: str = Form(...),
    source: Literal["live", "history", "json_payload"] = Form("live"),
    raw_payload: Optional[str] = Form(None),
    is_admin: bool = Depends(verify_admin_permission)
):
    project = await projects_collection.find_one({"projectId": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    default_class = project["classes"][0]
    source_records = []

    if source == "live":
        source_records = await collection.find({}, {"_id": 0}).to_list(100000)
    elif source == "history":
        source_records = await history_collection.find({}, {"_id": 0}).to_list(100000)
    elif source == "json_payload":
        if not raw_payload:
            raise HTTPException(status_code=400, detail="JSON Payload required when source='json_payload'")
        try:
            parsed = json.loads(raw_payload)
            source_records = parsed if isinstance(parsed, list) else parsed.get("records", [])
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid JSON Format: {str(e)}")

    imported_count = 0
    for doc in source_records:
        post_url = doc.get("postUrl", "")
        if not post_url:
            continue

        exists = await dataset_collection.find_one({"projectId": project_id, "postUrl": post_url})
        if not exists:
            item_doc = {
                "projectId": project_id,
                "postUrl": post_url,
                "profileName": doc.get("profileName", "Unknown"),
                "profileUrl": doc.get("profileUrl", ""),
                "privacyType": doc.get("privacyType", "Unknown"),
                "postDatetime": doc.get("postDatetime", ""),
                "imageUrl": doc.get("imageUrl", ""),
                "firstCapturedAt": doc.get("firstCapturedAt", doc.get("capturedAt", "")),
                "customClass": doc.get("customClass", default_class),
                "isVerified": False,
                "addedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            await dataset_collection.insert_one(item_doc)
            imported_count += 1

    return {"status": "success", "importedCount": imported_count, "source": source, "projectId": project_id}


# --- 7. INLINE EDIT ITEM METADATA & CLASS ---
@router.patch("/projects/update-item", summary="[Admin] Edit Metadata / Class Label")
async def update_project_item(
    project_id: str = Form(...),
    original_post_url: str = Form(...),
    profileName: Optional[str] = Form(None),
    privacyType: Optional[str] = Form(None),
    customClass: Optional[str] = Form(None),
    is_admin: bool = Depends(verify_admin_permission)
):
    project = await projects_collection.find_one({"projectId": project_id})
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    update_fields = {"isVerified": True}

    if profileName is not None:
        update_fields["profileName"] = profileName
    if privacyType is not None:
        update_fields["privacyType"] = privacyType
    if customClass is not None:
        if customClass not in project["classes"]:
            raise HTTPException(status_code=400, detail=f"Class '{customClass}' is not in project schema.")
        update_fields["customClass"] = customClass

    res = await dataset_collection.update_one(
        {"projectId": project_id, "postUrl": original_post_url},
        {"$set": update_fields}
    )

    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Item not found in project.")

    return {"status": "success", "updatedFields": update_fields}


# --- 8. EXPORT ZIP ARCHIVE WITH DETAILED ERROR PREVENTIONS ---
@router.get("/projects/export-zip", summary="[Admin] Export Project ZIP Archive")
async def export_project_zip(
    project_id: str = Query(...),
    mode: Literal["full", "metadata_only"] = Query("full"),
    is_admin: bool = Depends(verify_admin_permission)
):
    project = await projects_collection.find_one({"projectId": project_id})
    if not project:
        raise HTTPException(status_code=404, detail=f"Project '{project_id}' not found.")

    items = await dataset_collection.find({"projectId": project_id}, {"_id": 0}).to_list(100000)
    if not items:
        raise HTTPException(status_code=400, detail=f"Project '{project_id}' has no items to export.")

    zip_buffer = io.BytesIO()

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        
        # A. Always include JSON manifest
        manifest_data = json.dumps({
            "project": project,
            "exportMode": mode,
            "exportedAt": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "version": APP_VERSION,
            "records": items
        }, indent=2, ensure_ascii=False)
        zf.writestr(f"{project_id}/dataset_manifest.json", manifest_data)

        # B. Always include CSV index with Hyperlinks
        csv_buffer = io.StringIO()
        csv_writer = csv.DictWriter(csv_buffer, fieldnames=[
            "postUrl", "profileName", "privacyType", "customClass", "isVerified", "imageUrl", "firstCapturedAt"
        ])
        csv_writer.writeheader()
        for item in items:
            csv_writer.writerow({
                "postUrl": item.get("postUrl", ""),
                "profileName": item.get("profileName", ""),
                "privacyType": item.get("privacyType", ""),
                "customClass": item.get("customClass", ""),
                "isVerified": item.get("isVerified", False),
                "imageUrl": item.get("imageUrl", ""),
                "firstCapturedAt": item.get("firstCapturedAt", "")
            })
        zf.writestr(f"{project_id}/dataset_index.csv", csv_buffer.getvalue())

        # C. Bundle Images if Mode is Full
        if mode == "full":
            disk_map = {}
            if os.path.exists(IMAGE_DIR):
                for fname in os.listdir(IMAGE_DIR):
                    disk_map[fname.lower()] = os.path.join(IMAGE_DIR, fname)

            for idx, item in enumerate(items, start=1):
                img_url = item.get("imageUrl", "")
                assigned_class = item.get("customClass", "unlabeled")

                if not img_url:
                    continue

                parsed = urllib.parse.urlparse(img_url)
                base_fname = os.path.basename(parsed.path) or f"image_{idx}.png"
                arc_path = f"{project_id}/{assigned_class}/{base_fname}"

                # Check if file exists on disk
                disk_path = disk_map.get(base_fname.lower())
                if disk_path and os.path.isfile(disk_path):
                    zf.write(disk_path, arcname=arc_path)

    zip_buffer.seek(0)
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    out_filename = f"{project_id}_{mode}_v{APP_VERSION}_{timestamp_str}.zip"

    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={out_filename}",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )