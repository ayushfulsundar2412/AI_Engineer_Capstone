import logging
import re
from typing import Callable, TypeVar

from pydantic import BaseModel, ValidationError

from app.llm_core.backends import get_backend

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)
Backend = Callable[[str, str, dict | None], str]


class LLMOutputError(Exception):
    """Raised when the model never produced a valid answer."""


def ask(system: str, user: str, backend: Backend | None = None) -> str:
    """Ask for free text."""
    backend = backend or get_backend()
    return backend(system, user, None)


def _extract_json(text: str) -> str:
    """Models sometimes wrap JSON in markdown fences; remove them."""
    text = text.strip()
    match = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    return match.group(1).strip() if match else text


def ask_structured(
    system: str,
    user: str,
    model: type[T],
    backend: Backend | None = None,
    max_attempts: int = 3,
) -> T:
    """Ask for an answer in the shape of `model`, checking it and retrying."""
    backend = backend or get_backend()
    schema = model.model_json_schema()
    prompt = user
    last_error = ""

    for attempt in range(1, max_attempts + 1):
        raw = backend(system, prompt, schema)
        try:
            return model.model_validate_json(_extract_json(raw))
        except ValidationError as exc:
            last_error = str(exc)[:300]
            logger.warning("LLM reply invalid (attempt %s of %s)", attempt, max_attempts)
            prompt = (
                f"{user}\n\nYour previous reply was invalid:\n{last_error}\n"
                "Reply again with only valid JSON in the required shape."
            )

    raise LLMOutputError(f"No valid answer after {max_attempts} attempts: {last_error}")