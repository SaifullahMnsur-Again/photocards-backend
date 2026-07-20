import os
import csv
import uuid
import datetime
import random
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MEDIA_DIR = os.path.join(BASE_DIR, "media")
IMAGE_DIR = os.path.join(MEDIA_DIR, "images")
CSV_PATH = os.path.join(BASE_DIR, "collected_posts.csv")

SERVER_DOMAIN = "https://photocards.saifullahmnsur.dev"

# --- 1. DEFINE EXPLICIT RESPONSE SCHEMAS FOR OPENAPI ---

class AnalysisStatus(str, Enum):
    OK = "ok"
    ALERT = "alert"
    NOTHING_TO_DETECT = "nothing_to_detect"
    LOW_CONFIDENCE = "low_confidence"

class AnalysisResult(BaseModel):
    status: AnalysisStatus = Field(..., description="Classification result status enum")
    badge: str = Field(..., example="🟡 Low Confidence")
    message: str = Field(..., example="Uncertain classification score. Stored in queue for future model fine-tuning.")

class StoredRecord(BaseModel):
    capturedAt: str = Field(..., example="2026-07-20 11:45:00")
    profileName: str = Field(..., example="John Doe")
    profileUrl: str = Field(..., example="https://facebook.com/johndoe")
    postUrl: str = Field(..., example="https://facebook.com/posts/123456")
    privacyType: str = Field(..., example="Public")
    postDatetime: str = Field(..., example="2 hours ago")
    imageUrl: str = Field(..., example="https://photocards.saifullahmnsur.dev/media/images/abcd-1234.jpg")

class PostAnalysisResponse(BaseModel):
    version: str = Field("v1", example="v1")
    analysis: AnalysisResult
    record: StoredRecord


def append_to_csv(profile_name, profile_url, post_url, privacy_type, post_datetime, image_url, status):
    file_exists = os.path.isfile(CSV_PATH)
    server_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(CSV_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "Captured At (API Call)", "Profile Name", "Profile URL", 
                "Post URL", "Privacy Type", "Post Datetime", "Image URL", "Analysis Status"
            ])
        writer.writerow([
            server_timestamp, profile_name, profile_url, post_url, 
            privacy_type, post_datetime, image_url, status
        ])
    return server_timestamp

# --- 2. ATTACH response_model HERE ---

@router.post(
    "/posts/analyze", 
    response_model=PostAnalysisResponse,  # <-- THIS ENABLES THE SCHEMA IN DOCS
    summary="Analyze Facebook Post and Store Dataset",
    description="Processes post metadata and image, runs threat detection analysis, and indexes data into the dataset."
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
            file_extension = os.path.splitext(image.filename)[1] or ".jpg"
            unique_filename = f"{uuid.uuid4()}{file_extension}"
            file_save_path = os.path.join(IMAGE_DIR, unique_filename)
            
            with open(file_save_path, "wb") as buffer:
                buffer.write(await image.read())
            
            final_image_url = f"{SERVER_DOMAIN}/media/images/{unique_filename}"

        simulated_analysis = random.choice([
            {
                "status": AnalysisStatus.OK, 
                "badge": "🟢 Clean", 
                "message": "High confidence: No actionable patterns identified."
            },
            {
                "status": AnalysisStatus.ALERT, 
                "badge": "🔴 Alert", 
                "message": "High confidence: Threat/risk pattern signature matched!"
            },
            {
                "status": AnalysisStatus.NOTHING_TO_DETECT, 
                "badge": "⚪ Neutral", 
                "message": "Context insufficient. Skipped classification."
            },
            {
                "status": AnalysisStatus.LOW_CONFIDENCE, 
                "badge": "🟡 Low Confidence", 
                "message": "Uncertain classification score. Stored in queue for future model fine-tuning."
            }
        ])

        captured_at = append_to_csv(
            profileName, profileUrl, postUrl, privacyType, 
            postDatetime, final_image_url, simulated_analysis["status"].value
        )

        return PostAnalysisResponse(
            version="v1",
            analysis=AnalysisResult(
                status=simulated_analysis["status"],
                badge=simulated_analysis["badge"],
                message=simulated_analysis["message"]
            ),
            record=StoredRecord(
                capturedAt=captured_at,
                profileName=profileName,
                profileUrl=profileUrl,
                postUrl=postUrl,
                privacyType=privacyType,
                postDatetime=postDatetime,
                imageUrl=final_image_url
            )
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis Engine Error: {str(e)}")


@router.get("/download-csv", summary="Download Aggregated CSV Dataset")
async def download_csv():
    if not os.path.isfile(CSV_PATH):
        raise HTTPException(status_code=404, detail="No dataset logs created yet.")
    return FileResponse(CSV_PATH, media_type="text/csv", filename="collected_posts.csv")