import os
import csv
import uuid
import datetime
import random
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse

router = APIRouter()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MEDIA_DIR = os.path.join(BASE_DIR, "media")
IMAGE_DIR = os.path.join(MEDIA_DIR, "images")
CSV_PATH = os.path.join(BASE_DIR, "collected_posts.csv")

SERVER_DOMAIN = "https://photocards.saifullahmnsur.dev"

def append_to_csv(profile_name, profile_url, post_url, privacy_type, post_datetime, image_url):
    file_exists = os.path.isfile(CSV_PATH)
    server_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(CSV_PATH, mode="a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow([
                "Captured At (API Call)", "Profile Name", "Profile URL", 
                "Post URL", "Privacy Type", "Post Datetime", "Image URL"
            ])
        writer.writerow([
            server_timestamp, profile_name, profile_url, post_url, 
            privacy_type, post_datetime, image_url
        ])
    return server_timestamp

# --- PRIMARY ANALYSIS ENDPOINT ---
# Route: POST /api/v1/posts/analyze
@router.post("/posts/analyze")
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

        # Persist post record for dataset aggregation
        captured_at = append_to_csv(profileName, profileUrl, postUrl, privacyType, postDatetime, final_image_url)

        # Post analysis simulation
        simulated_analysis = random.choice([
            {"status": "ok", "badge": "🟢 Clean", "message": "No actionable flags detected during analysis."},
            {"status": "alert", "badge": "🔴 Alert", "message": "High-risk pattern signature detected!"},
            {"status": "nothing_to_detect", "badge": "⚪ Neutral", "message": "No specific features identified in analysis."}
        ])

        return {
            "version": "v1",
            "analysis": {
                "status": simulated_analysis["status"],
                "badge": simulated_analysis["badge"],
                "message": simulated_analysis["message"],
            },
            "record": {
                "capturedAt": captured_at,
                "profileName": profileName,
                "profileUrl": profileUrl,
                "postUrl": postUrl,
                "privacyType": privacyType,
                "postDatetime": postDatetime,
                "imageUrl": final_image_url
            }
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis Engine Error: {str(e)}")

# Route: GET /api/v1/download-csv
@router.get("/download-csv")
async def download_csv():
    if not os.path.isfile(CSV_PATH):
        raise HTTPException(status_code=404, detail="No dataset logs created yet.")
    return FileResponse(CSV_PATH, media_type="text/csv", filename="collected_posts.csv")