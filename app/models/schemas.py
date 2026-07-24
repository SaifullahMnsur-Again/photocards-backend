from enum import Enum
from typing import Optional, List, Dict, Any
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

class PipelineStageStatus(str, Enum):
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"

class DetectionBox(BaseModel):
    class_id: int
    class_name: str
    confidence: float
    bbox: List[int]  # [x1, y1, x2, y2]

class StageResult(BaseModel):
    stage_name: str
    status: PipelineStageStatus
    message: str
    execution_time_ms: float
    data: Optional[Dict[str, Any]] = None

class FinalVerdict(BaseModel):
    class_id: int
    status_label: str  # VERIFIED_REAL, MISLEADING_EDIT, FABRICATED_FAKE, LOW_CONFIDENCE
    badge: str
    confidence_score: float
    news_authenticity_score: float
    reason: str

class VisualCheckerResponse(BaseModel):
    request_id: str
    image_url: str
    stages: List[StageResult]
    verdict: FinalVerdict