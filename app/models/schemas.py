from enum import Enum
from typing import Optional
from pydantic import BaseModel

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
    firstCapturedAt: str
    lastCapturedAt: str
    requestCount: int = 1
    profileName: str
    profileUrl: str
    postUrl: str
    privacyType: str
    postDatetime: str
    imageUrl: str
    status: Optional[str] = "low_confidence"

class PostAnalysisResponse(BaseModel):
    version: str = "v1"
    isCachedResponse: bool = False
    analysis: AnalysisResult
    record: StoredRecord