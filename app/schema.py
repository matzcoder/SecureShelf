"""Request and response models. Empty for now; you add these from Session 4."""

from typing import Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    messages: list["ChatMessage"] = Field(min_length=1)
    model: str = "examate-fake"


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str