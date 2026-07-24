import os
import uuid
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.config import IMAGE_DIR, SERVER_DOMAIN
from app.db import collection
from app.models.schemas import PostAnalysisResponse, AnalysisResult, StoredRecord
from app.core.pipeline import evaluate_analysis_pipeline

router = APIRouter()

DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

def should_reanalyze(first_captured_dt: datetime, last_captured_dt: datetime, now_dt: datetime) -> bool:
    """
    Calculates if enough time has passed to trigger re-analysis 
    based on the total age of the post in the DB.
    """
    age = now_dt - first_captured_dt
    time_since_last_analysis = now_dt - last_captured_dt

    if age <= timedelta(hours=1):
        # Initial Phase: Re-analyze if > 2 minutes since last analysis
        return time_since_last_analysis >= timedelta(minutes=2)
    elif age <= timedelta(days=1):
        # Short Term: Re-analyze if > 6 hours
        return time_since_last_analysis >= timedelta(hours=6)
    elif age <= timedelta(days=7):
        # Mid Term: Re-analyze if > 2 days
        return time_since_last_analysis >= timedelta(days=2)
    else:
        # Long Term / Capped Max: Re-analyze if > 7 days
        return time_since_last_analysis >= timedelta(days=7)


# app/api/v1/analyze.py

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
        now_dt = datetime.now()
        now_str = now_dt.strftime(DATE_FORMAT)

        # 1. Check if postUrl already exists in database
        existing_record = await collection.find_one({"postUrl": postUrl})

        if existing_record:
            first_captured_dt = datetime.strptime(existing_record.get("firstCapturedAt", now_str), DATE_FORMAT)
            last_captured_dt = datetime.strptime(existing_record.get("lastCapturedAt", now_str), DATE_FORMAT)

            if not should_reanalyze(first_captured_dt, last_captured_dt, now_dt):
                updated_count = existing_record.get("requestCount", 1) + 1
                await collection.update_one(
                    {"_id": existing_record["_id"]},
                    {"$set": {"requestCount": updated_count}}
                )

                stored_doc = StoredRecord(
                    firstCapturedAt=existing_record.get("firstCapturedAt", now_str),
                    lastCapturedAt=existing_record.get("lastCapturedAt", now_str),
                    requestCount=updated_count,
                    profileName=existing_record.get("profileName", profileName),
                    profileUrl=existing_record.get("profileUrl", profileUrl),
                    postUrl=postUrl,
                    privacyType=existing_record.get("privacyType", privacyType),
                    postDatetime=existing_record.get("postDatetime", postDatetime),
                    imageUrl=existing_record.get("imageUrl", ""),
                    status=existing_record.get("status", "low_confidence")
                )

                badge_map = {
                    "ok": "🟢 Verified Real",
                    "alert": "🔴 Fabricated Fake",
                    "low_confidence": "🟡 Low Confidence"
                }

                return PostAnalysisResponse(
                    version="v1",
                    isCachedResponse=True,
                    analysis=AnalysisResult(
                        status=stored_doc.status,
                        badge=badge_map.get(stored_doc.status, "🟡 Low Confidence"),
                        message=f"Cached analysis returned. Request count: {updated_count}",
                        stages=[],
                        verdict={}
                    ),
                    record=stored_doc
                )

        # 2. Fresh Analysis Execution Path
        final_image_url = existing_record.get("imageUrl", "") if existing_record else ""
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

        # Runs the 5-stage evaluation pipeline
        analysis_result = await evaluate_analysis_pipeline(file_save_path, metadata)
        pipeline_status = analysis_result.get("status", "low_confidence")

        if existing_record:
            first_captured_str = existing_record.get("firstCapturedAt", now_str)
            new_count = existing_record.get("requestCount", 1) + 1
            
            update_payload = {
                "lastCapturedAt": now_str,
                "requestCount": new_count,
                "status": pipeline_status
            }
            if final_image_url:
                update_payload["imageUrl"] = final_image_url

            await collection.update_one({"_id": existing_record["_id"]}, {"$set": update_payload})

            stored_doc = StoredRecord(
                firstCapturedAt=first_captured_str,
                lastCapturedAt=now_str,
                requestCount=new_count,
                profileName=profileName,
                profileUrl=profileUrl,
                postUrl=postUrl,
                privacyType=privacyType,
                postDatetime=postDatetime,
                imageUrl=final_image_url or existing_record.get("imageUrl", ""),
                status=pipeline_status
            )
        else:
            doc_dict = {
                "firstCapturedAt": now_str,
                "lastCapturedAt": now_str,
                "requestCount": 1,
                "profileName": profileName,
                "profileUrl": profileUrl,
                "postUrl": postUrl,
                "privacyType": privacyType,
                "postDatetime": postDatetime,
                "imageUrl": final_image_url,
                "status": pipeline_status
            }
            await collection.insert_one(doc_dict)
            stored_doc = StoredRecord(**doc_dict)

        return PostAnalysisResponse(
            version="v1",
            isCachedResponse=False,
            analysis=AnalysisResult(
                status=pipeline_status,
                badge=analysis_result.get("badge", "🟡 Low Confidence"),
                message=analysis_result.get("message", ""),
                stages=analysis_result.get("stages", []),
                verdict=analysis_result.get("verdict", {})
            ),
            record=stored_doc
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis Engine Error: {str(e)}")

import os
import uuid
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import StreamingResponse
from app.config import MEDIA_DIR, SERVER_DOMAIN
from app.core.pipeline import evaluate_analysis_pipeline_stream

router = APIRouter()

IMAGE_DIR = os.path.join(MEDIA_DIR, "images")
os.makedirs(IMAGE_DIR, exist_ok=True)

@router.post("/posts/analyze-stream")
async def analyze_post_stream(
    profileName: str = Form("Anonymous"),
    profileUrl: str = Form(""),
    postUrl: str = Form(""),
    privacyType: str = Form("Public"),
    postDatetime: str = Form(""),
    image: UploadFile = File(...)
):
    """
    Streams analysis updates in real-time line-by-line JSON (Server-Sent Events).
    """
    if not image:
        raise HTTPException(status_code=400, detail="Missing mandatory image file.")

    file_extension = os.path.splitext(image.filename)[1] or ".png"
    unique_filename = f"{uuid.uuid4()}{file_extension}"
    file_save_path = os.path.join(IMAGE_DIR, unique_filename)

    with open(file_save_path, "wb") as buffer:
        buffer.write(await image.read())

    metadata = {
        "profileName": profileName,
        "profileUrl": profileUrl,
        "postUrl": postUrl,
        "privacyType": privacyType,
        "postDatetime": postDatetime,
        "imageUrl": f"{SERVER_DOMAIN}/media/images/{unique_filename}"
    }

    return StreamingResponse(
        evaluate_analysis_pipeline_stream(file_save_path, metadata),
        media_type="application/x-ndjson"
    )