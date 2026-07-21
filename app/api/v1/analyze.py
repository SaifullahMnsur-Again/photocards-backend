import os
import uuid
import datetime
import io
import csv
from enum import Enum
from typing import Optional, Literal, Dict, Any, List
from pydantic import BaseModel, Field
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient

router = APIRouter()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGO_URI)
db = client["photocards_db"]
collection = db["posts"]

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
MEDIA_DIR = os.path.join(BASE_DIR, "media")
IMAGE_DIR = os.path.join(MEDIA_DIR, "images")
os.makedirs(IMAGE_DIR, exist_ok=True)

SERVER_DOMAIN = "https://photocards.saifullahmnsur.dev"

class AnalysisStatus(str, Enum):
    OK = "ok"
    ALERT = "alert"
    NOTHING_TO_DETECT = "nothing_to_detect"
    LOW_CONFIDENCE = "low_confidence"

class AnalysisResult(BaseModel):
    status: AnalysisStatus
    badge: str
    message: str

class StoredRecord(BaseModel):
    capturedAt: str
    profileName: str
    profileUrl: str
    postUrl: str
    privacyType: str
    postDatetime: str
    imageUrl: str
    status: Optional[str] = "low_confidence"

class PostAnalysisResponse(BaseModel):
    version: str = "v1"
    analysis: AnalysisResult
    record: StoredRecord


# --- 1. ANALYSIS METHOD (RETURNS FINAL RESULT TO ANALYZE ROUTE) ---
async def evaluate_analysis_pipeline(image_path: Optional[str], metadata: dict) -> dict:
    """
    Evaluates content and returns the final analysis result dict.
    Currently defaults to 'low_confidence' until models/methods are implemented.
    """
    return {
        "status": AnalysisStatus.LOW_CONFIDENCE,
        "badge": "🟡 Low Confidence",
        "message": "Analysis pipeline models not yet implemented. Logged for dataset training."
    }


# --- 2. PRIMARY ANALYZE ROUTE ---
@router.post("/posts/analyze", response_model=PostAnalysisResponse)
async def analyze_post(
    profileName: str = Form(...),
    profileUrl: str = Form(...),
    postUrl: str = Form(...),
    privacyType: str = Form(...),
    postDatetime: str = Form(...),
    image: UploadFile = File(None)
):
    try:
        final_image_url = ""
        file_save_path = ""

        if image:
            file_extension = os.path.splitext(image.filename)[1] or ".png"
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            file_save_path = os.path.join(IMAGE_DIR, unique_filename)
            
            with open(file_save_path, "wb") as buffer:
                buffer.write(await image.read())
            
            final_image_url = f"{SERVER_DOMAIN}/media/images/{unique_filename}"

        metadata = {
            "profileName": profileName,
            "profileUrl": profileUrl,
            "postUrl": postUrl,
            "privacyType": privacyType,
            "postDatetime": postDatetime
        }

        # Collect final result from the analysis method above
        analysis_result = await evaluate_analysis_pipeline(file_save_path, metadata)
        server_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        record_dict = {
            "capturedAt": server_timestamp,
            "profileName": profileName,
            "profileUrl": profileUrl,
            "postUrl": postUrl,
            "privacyType": privacyType,
            "postDatetime": postDatetime,
            "imageUrl": final_image_url,
            "status": analysis_result["status"].value
        }

        # Index into MongoDB dataset
        await collection.insert_one(record_dict)

        return PostAnalysisResponse(
            version="v1",
            analysis=AnalysisResult(
                status=analysis_result["status"],
                badge=analysis_result["badge"],
                message=analysis_result["message"]
            ),
            record=StoredRecord(**record_dict)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis Engine Error: {str(e)}")


# --- 3. DYNAMIC QUERY BUILDER FOR DATASET DOWNLOAD ---
def build_advanced_mongo_query(filters_list: List[Dict[str, str]]) -> Dict[str, Any]:
    query: Dict[str, Any] = {}

    for f in filters_list:
        mode = f.get("mode", "inc")
        param = f.get("param", "")
        val = f.get("val", "").strip()

        if not param or not val:
            continue

        if param == "status":
            if mode == "inc":
                query["status"] = val
            else:
                query["status"] = {"$ne": val}

        elif param == "privacyType":
            if mode == "inc":
                query["privacyType"] = {"$regex": val, "$options": "i"}
            else:
                query["privacyType"] = {"$not": {"$regex": val, "$options": "i"}}

        elif param in ["profileName", "profileUrl", "postUrl"]:
            if mode == "inc":
                query[param] = {"$regex": val, "$options": "i"}
            else:
                query[param] = {"$not": {"$regex": val, "$options": "i"}}

        elif param == "start_date":
            query.setdefault("capturedAt", {})["$gte"] = f"{val} 00:00:00"

        elif param == "end_date":
            query.setdefault("capturedAt", {})["$lte"] = f"{val} 23:59:59"

    return query


# --- 4. DATASET DOWNLOAD METHOD ---
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

    # JSON Download
    if format == "json":
        import json
        json_bytes = json.dumps(records, indent=2, ensure_ascii=False).encode("utf-8")
        return StreamingResponse(
            io.BytesIO(json_bytes),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=photocard_dataset_{timestamp_str}.json"}
        )

    # CSV Download
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