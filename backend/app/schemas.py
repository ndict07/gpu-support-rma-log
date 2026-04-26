from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import MessageType


class RmaThreadCreate(BaseModel):
    rma_number: str = Field(max_length=255)
    title: str | None = Field(default=None, max_length=255)
    customer_name: str | None = Field(default=None, max_length=255)

    @field_validator("rma_number")
    @classmethod
    def validate_rma_number(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("rma_number is required")
        return value

    @field_validator("title", "customer_name")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class RmaThreadUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    customer_name: str | None = Field(default=None, max_length=255)

    @field_validator("title", "customer_name")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class RmaThreadRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rma_number: str
    title: str | None = None
    customer_name: str | None = None
    created_at: datetime
    updated_at: datetime
    latest_message_preview: str | None = None


class RmaThreadListResponse(BaseModel):
    items: list[RmaThreadRead]
    total: int
    limit: int
    offset: int


class MessageCreate(BaseModel):
    type: MessageType
    content: str = ""

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        value = value.strip()
        return value


class MessageUpdate(BaseModel):
    type: MessageType
    content: str

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        return value.strip()


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rma_thread_id: str
    type: MessageType
    content: str
    attachment_url: str | None = None
    attachment_filename: str | None = None
    attachment_mime_type: str | None = None
    attachment_size: int | None = None
    created_at: datetime


class RmaThreadBoardItem(RmaThreadRead):
    messages: list[MessageRead]


class BoardResponse(BaseModel):
    items: list[RmaThreadBoardItem]
    total: int
    limit: int
    offset: int
