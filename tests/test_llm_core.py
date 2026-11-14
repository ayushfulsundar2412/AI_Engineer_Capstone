import pytest

from app.llm_core import LLMOutputError, ask, ask_structured
from app.llm_core.backends import get_backend
from app.llm_core.models import RiskAssessment

GOOD = (
    '{"risk_level": "high", "explanation": "SSH is open to the world.", '
    '"recommendation": "Restrict the source range."}'
)


class ScriptedBackend:
    """A fake model: returns prepared replies in order and records every call."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, system, user, json_schema=None):
        self.calls.append((system, user, json_schema))
        return self.replies.pop(0)


def test_ask_returns_the_backend_text():
    backend = ScriptedBackend(["hello"])
    assert ask("sys", "hi", backend=backend) == "hello"
    assert backend.calls[0][2] is None  # free text: no schema sent


def test_structured_valid_on_first_try():
    backend = ScriptedBackend([GOOD])
    result = ask_structured("sys", "data", RiskAssessment, backend=backend)
    assert result.risk_level == "high"
    assert len(backend.calls) == 1
    assert backend.calls[0][2] is not None  # the schema was sent


def test_structured_strips_markdown_fences():
    backend = ScriptedBackend(["```json\n" + GOOD + "\n```"])
    result = ask_structured("sys", "data", RiskAssessment, backend=backend)
    assert result.risk_level == "high"


def test_structured_retries_after_invalid_reply():
    backend = ScriptedBackend(["not json at all", GOOD])
    result = ask_structured("sys", "data", RiskAssessment, backend=backend)
    assert result.risk_level == "high"
    assert len(backend.calls) == 2
    assert "invalid" in backend.calls[1][1]  # the retry prompt explains the problem


def test_structured_rejects_value_outside_allowed_choices():
    bad = GOOD.replace('"high"', '"catastrophic"')
    backend = ScriptedBackend([bad, GOOD])
    result = ask_structured("sys", "data", RiskAssessment, backend=backend)
    assert result.risk_level == "high"
    assert len(backend.calls) == 2


def test_structured_gives_up_after_max_attempts():
    backend = ScriptedBackend(["nope", "nope", "nope"])
    with pytest.raises(LLMOutputError):
        ask_structured("sys", "data", RiskAssessment, backend=backend)
    assert len(backend.calls) == 3


def test_unknown_backend_name_is_rejected(monkeypatch):
    monkeypatch.setenv("LLM_BACKEND", "does-not-exist")
    with pytest.raises(ValueError):
        get_backend()