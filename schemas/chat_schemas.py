"""Pydantic schemas for the chat endpoints."""

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Body of POST /api/v1/chat sent by the Flutter client."""

    chat_title: str = Field(..., min_length=1, max_length=80, examples=["vedic_remedies"])
    message: str = Field(..., min_length=1, max_length=4000)


class ChatResponse(BaseModel):
    """Non-streaming chat reply (when ?stream=false)."""

    success: bool = True
    answer: str
    vector_id: str = Field(examples=["usr_9f82a_vedic_remedies_001"])
