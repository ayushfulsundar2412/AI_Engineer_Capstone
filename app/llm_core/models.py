from typing import Literal

from pydantic import BaseModel, Field


class RiskAssessment(BaseModel):
    """The shape every risk answer must have."""

    risk_level: Literal["low", "medium", "high"]
    explanation: str = Field(min_length=1, max_length=500)
    recommendation: str = Field(min_length=1, max_length=500)