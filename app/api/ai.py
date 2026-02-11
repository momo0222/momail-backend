from fastapi import APIRouter, HTTPException, Depends
from app.schemas.ai import GenerateEmailRequest, GenerateEmailResponse
from app.services.ai_service import ai_service
import logging

router = APIRouter()

@router.post("/generate-email", response_model = GenerateEmailResponse)
def get(
    request: GenerateEmailRequest,
):
    """
    Generate email content with AI
    """
    try:
        generated_text = ai_service.generate_email(
                to=request.to,
                subject=request.subject,
                tone=request.tone,
                instructions=request.instructions,
                attached_files=request.attached_files,
                enable_research=request.enable_research
        )

        return GenerateEmailResponse(
            suggested_reply=generated_text,
            research_used=request.enable_research
        )
    except Exception as e:
        # Unexpected errors -> 500
        logging.error(f"Unexpected error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail="An unexpected error occurred"
        )