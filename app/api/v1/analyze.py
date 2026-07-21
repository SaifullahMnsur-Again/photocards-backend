import os
import uuid
import datetime
from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from app.config import IMAGE_DIR, SERVER_DOMAIN
from app.db import collection
from app.models.schemas import PostAnalysisResponse, AnalysisResult, StoredRecord
from app.core.pipeline import evaluate_analysis_pipeline

router = APIRouter()

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

        # Collect analysis state from modular pipeline
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

        # Save to MongoDB
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