import os
import uuid
import datetime
import random
import io
import csv
from enum import Enum
from typing import Optional, Literal, Dict, Any
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

class SortOrder(str, Enum):
    ASC = "asc"
    DESC = "desc"

class SortField(str, Enum):
    CAPTURED_AT = "capturedAt"
    PROFILE_NAME = "profileName"
    POST_DATETIME = "postDatetime"

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
    status: Optional[str] = "ok"

class PostAnalysisResponse(BaseModel):
    version: str = "v1"
    analysis: AnalysisResult
    record: StoredRecord

def build_mongo_query(
    search: Optional[str] = None,
    status: Optional[str] = None,
    privacy: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
) -> Dict[str, Any]:
    query: Dict[str, Any] = {}

    if search:
        query["$or"] = [
            {"profileName": {"$regex": search, "$options": "i"}},
            {"postUrl": {"$regex": search, "$options": "i"}}
        ]
    if status and status != "all":
        query["status"] = status
    if privacy and privacy != "all":
        query["privacyType"] = {"$regex": privacy, "$options": "i"}
    
    if start_date or end_date:
        date_query = {}
        if start_date:
            date_query["$gte"] = f"{start_date} 00:00:00"
        if end_date:
            date_query["$lte"] = f"{end_date} 23:59:59"
        query["capturedAt"] = date_query

    return query

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

        if image:
            file_extension = os.path.splitext(image.filename)[1] or ".png"
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            file_save_path = os.path.join(IMAGE_DIR, unique_filename)
            
            with open(file_save_path, "wb") as buffer:
                buffer.write(await image.read())
            
            final_image_url = f"{SERVER_DOMAIN}/media/images/{unique_filename}"

        simulated_analysis = random.choice([
            {"status": AnalysisStatus.OK, "badge": "🟢 Clean", "message": "High confidence: No actionable patterns identified."},
            {"status": AnalysisStatus.ALERT, "badge": "🔴 Alert", "message": "High confidence: Threat/risk pattern signature matched!"},
            {"status": AnalysisStatus.NOTHING_TO_DETECT, "badge": "⚪ Neutral", "message": "Context insufficient. Skipped classification."},
            {"status": AnalysisStatus.LOW_CONFIDENCE, "badge": "🟡 Low Confidence", "message": "Uncertain classification score. Stored in queue for future model fine-tuning."}
        ])

        server_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        record_dict = {
            "capturedAt": server_timestamp,
            "profileName": profileName,
            "profileUrl": profileUrl,
            "postUrl": postUrl,
            "privacyType": privacyType,
            "postDatetime": postDatetime,
            "imageUrl": final_image_url,
            "status": simulated_analysis["status"].value
        }

        await collection.insert_one(record_dict)

        return PostAnalysisResponse(
            version="v1",
            analysis=AnalysisResult(
                status=simulated_analysis["status"],
                badge=simulated_analysis["badge"],
                message=simulated_analysis["message"]
            ),
            record=StoredRecord(**record_dict)
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis Engine Error: {str(e)}")

# --- CUSTOMIZED FILTER & DATASET DOWNLOAD ENDPOINT ---
@router.get("/dataset/download")
async def download_dataset(
    format: Literal["json", "csv"] = Query("json"),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    privacy: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    sort_by: SortField = Query(SortField.CAPTURED_AT),
    sort_order: SortOrder = Query(SortOrder.DESC)
):
    query = build_mongo_query(search, status, privacy, start_date, end_date)
    sort_dir = -1 if sort_order == SortOrder.DESC else 1

    cursor = collection.find(query, {"_id": 0}).sort(sort_by.value, sort_dir)
    records = await cursor.to_list(length=100000)

    if not records:
        raise HTTPException(status_code=404, detail="No matching dataset records found for export.")

    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    if format == "json":
        import json
        json_bytes = json.dumps(records, indent=2, ensure_ascii=False).encode("utf-8")
        return StreamingResponse(
            io.BytesIO(json_bytes),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=filtered_dataset_{timestamp_str}.json"}
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
            "status": row.get("status", "ok")
        })

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=filtered_dataset_{timestamp_str}.csv"}
    )