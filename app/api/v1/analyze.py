import os
import uuid
import datetime
import random
import io
import csv
from enum import Enum
from typing import Optional, Literal
from pydantic import BaseModel, Field
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import StreamingResponse
from motor.motor_asyncio import AsyncIOMotorClient

router = APIRouter()

# MongoDB Connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
client = AsyncIOMotorClient(MONGO_URI)
db = client["photocards_db"]
collection = db["posts"]

# Clean Base Path Resolution
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
MEDIA_DIR = os.path.join(BASE_DIR, "media")
IMAGE_DIR = os.path.join(MEDIA_DIR, "images")
os.makedirs(IMAGE_DIR, exist_ok=True)

SERVER_DOMAIN = "https://photocards.saifullahmnsur.dev"

# --- SCHEMAS ---

class AnalysisStatus(str, Enum):
    OK = "ok"
    ALERT = "alert"
    NOTHING_TO_DETECT = "nothing_to_detect"
    LOW_CONFIDENCE = "low_confidence"

class AnalysisResult(BaseModel):
    status: AnalysisStatus = Field(..., description="Classification status enum")
    badge: str = Field(..., example="🟡 Low Confidence")
    message: str = Field(..., example="Uncertain classification score. Stored in queue for future model fine-tuning.")

class StoredRecord(BaseModel):
    capturedAt: str = Field(..., example="2026-07-21 13:00:00")
    profileName: str = Field(..., example="John Doe")
    profileUrl: str = Field(..., example="https://facebook.com/johndoe")
    postUrl: str = Field(..., example="https://facebook.com/posts/12345")
    privacyType: str = Field(..., example="Public")
    postDatetime: str = Field(..., example="2 hours ago")
    imageUrl: str = Field(..., example="https://photocards.saifullahmnsur.dev/media/images/sample.jpg")
    status: Optional[str] = "ok"

class PostAnalysisResponse(BaseModel):
    version: str = "v1"
    analysis: AnalysisResult
    record: StoredRecord

# --- ENDPOINTS ---

@router.post(
    "/posts/analyze", 
    response_model=PostAnalysisResponse,
    summary="Analyze Facebook Post & Store in Dataset"
)
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


@router.get("/dataset/download", summary="Download Aggregated Dataset (JSON/CSV)")
async def download_dataset(
    format: Literal["json", "csv"] = Query("json", description="Export format: 'json' or 'csv'"),
    status_filter: Optional[AnalysisStatus] = Query(None, description="Filter dataset by status tag")
):
    query = {}
    if status_filter:
        query["status"] = status_filter.value

    cursor = collection.find(query, {"_id": 0})
    records = await cursor.to_list(length=100000)

    if not records:
        raise HTTPException(status_code=404, detail="No dataset records found.")

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
            "status": row.get("status", "ok")
        })

    output.seek(0)
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=photocard_dataset_{timestamp_str}.csv"}
    )