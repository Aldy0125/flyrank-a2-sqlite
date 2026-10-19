import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai_service import ClassificationResult, classify_message


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ai", tags=["AI"])


class ClassificationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=2000)

    @field_validator("text")
    @classmethod
    def validate_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be empty.")
        return value


@router.post("/classify", response_model=ClassificationResult)
def classify(request: ClassificationRequest):
    try:
        return classify_message(request.text)
    except RuntimeError as error:
        raise HTTPException(
            status_code=503,
            detail=str(error),
        ) from error
    except Exception as error:
        logger.exception("Unexpected classification failure")
        raise HTTPException(
            status_code=502,
            detail="AI classification failed.",
        ) from error
