from typing import Optional
from app.models.schemas import AnalysisStatus

async def evaluate_analysis_pipeline(image_path: Optional[str], metadata: dict) -> dict:
    """
    Evaluates incoming posts/images and returns final classification.
    Currently defaults to 'low_confidence' until models are integrated.
    """
    return {
        "status": AnalysisStatus.LOW_CONFIDENCE,
        "badge": "🟡 Low Confidence",
        "message": "Analysis pipeline models not yet implemented. Logged for dataset training."
    }