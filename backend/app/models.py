from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def new_uuid() -> str:
    return str(uuid.uuid4())


class MessageType(StrEnum):
    CUSTOMER = "customer_msg"
    SUPPORT = "support_msg"
    INTERNAL = "internal_memo"


class RmaThread(Base):
    __tablename__ = "rma_threads"

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_uuid)
    rma_number: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
    )

    messages: Mapped[list[Message]] = relationship(
        back_populates="thread",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (
        CheckConstraint(
            "type IN ('customer_msg', 'support_msg', 'internal_memo')",
            name="ck_messages_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(255), primary_key=True, default=new_uuid)
    rma_thread_id: Mapped[str] = mapped_column(
        String(255),
        ForeignKey("rma_threads.id", ondelete="CASCADE"),
        nullable=False,
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    attachment_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    attachment_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attachment_mime_type: Mapped[str | None] = mapped_column(String(255), nullable=True)
    attachment_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    thread: Mapped[RmaThread] = relationship(back_populates="messages")
