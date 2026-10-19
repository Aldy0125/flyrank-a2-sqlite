import json
import os
import random
import time
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from openai import (
    OpenAI,
    APIConnectionError,
    APITimeoutError,
    RateLimitError,
    InternalServerError,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError


BASE_DIR = Path(__file__).resolve().parent
PROMPT_PATH = BASE_DIR / "prompts" / "classify_v1.txt"

load_dotenv(BASE_DIR / ".env")


class ClassificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    category: Literal["billing", "bug", "feature", "other"]
    urgency: Literal["low", "normal", "high"]
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str = Field(min_length=1, max_length=240)


def classify_with_stub(text: str) -> ClassificationResult:
    """Predictable local classifier for development without API calls."""
    value = text.lower()

    billing_words = (
        "invoice", "billing", "payment", "refund", "charged", "charge"
    )
    bug_words = (
        "error", "crash", "broken", "bug", "not working", "does not work", "fails"
    )
    feature_words = (
        "feature", "please add", "would like", "support dark mode"
    )
    urgent_words = (
        "urgent", "critical", "outage", "completely blocked", "cannot log in"
    )

    if any(word in value for word in billing_words):
        category = "billing"
    elif any(word in value for word in bug_words):
        category = "bug"
    elif any(word in value for word in feature_words):
        category = "feature"
    else:
        category = "other"

    urgency = (
        "high" if any(word in value for word in urgent_words)
        else "normal"
    )

    return ClassificationResult(
        category=category,
        urgency=urgency,
        confidence=0.90 if category != "other" else 0.40,
        reason="Deterministic local stub result; no AI provider was called.",
    )


def call_model(prompt: str, text: str) -> str:
    api_key = os.getenv("LLM_API_KEY", "").strip()
    base_url = os.getenv(
        "LLM_BASE_URL", "https://openrouter.ai/api/v1"
    ).strip()
    model = os.getenv("LLM_MODEL", "").strip()

    if not api_key or api_key in {
        "PASTE_API_KEY_DI_SINI",
        "replace_with_your_api_key",
    }:
        raise RuntimeError("LLM_API_KEY is not configured.")

    if not model or model == "replace_with_model_id":
        raise RuntimeError("LLM_MODEL is not configured.")

    client = OpenAI(
        api_key=api_key,
        base_url=base_url,
        timeout=10.0,
        max_retries=0,
    )

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": text},
    ]

    for repair_attempt in range(2):
        last_error = None

        for network_attempt in range(3):
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0,
                    timeout=10.0,
                )

                content = response.choices[0].message.content
                if not content:
                    raise ValueError("The model returned empty content.")

                break

            except (
                APITimeoutError,
                APIConnectionError,
                RateLimitError,
                InternalServerError,
            ) as error:
                last_error = error

                if network_attempt == 2:
                    raise RuntimeError(
                        "AI provider failed after bounded retries."
                    ) from error

                time.sleep(
                    min(0.5 * (2 ** network_attempt) + random.random() * 0.1, 2)
                )

        else:
            raise RuntimeError("AI request failed.") from last_error

        try:
            parsed = json.loads(content)
            validated = ClassificationResult.model_validate(parsed)
            return validated.model_dump_json()

        except (json.JSONDecodeError, ValidationError, ValueError) as error:
            if repair_attempt == 1:
                raise RuntimeError(
                    "Model output remained invalid after one repair attempt."
                ) from error

            messages.extend([
                {"role": "assistant", "content": content},
                {
                    "role": "user",
                    "content": (
                        "Your previous response failed JSON/schema validation. "
                        "Return a corrected JSON object with exactly the "
                        "required fields. Do not add Markdown or commentary."
                    ),
                },
            ])

    raise RuntimeError("Unable to obtain a valid classification.")


def classify_message(text: str) -> ClassificationResult:
    if os.getenv("LLM_STUB", "1").strip() == "1":
        return classify_with_stub(text)

    if os.getenv("AI_ENABLED", "false").strip().lower() != "true":
        raise RuntimeError("AI is disabled by configuration.")

    prompt = PROMPT_PATH.read_text(encoding="utf-8-sig")
    output = call_model(prompt, text)
    return ClassificationResult.model_validate_json(output)

