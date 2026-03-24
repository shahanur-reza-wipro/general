from dataclasses import dataclass
from datetime import datetime
import uuid

from sqlalchemy import UUID, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .model import ModelBase


@dataclass
class DunningLetter(ModelBase):
    """DunningLetter model – represents a single dunning letter request sent to OpenText."""

    __tablename__ = "dunning_letter"

    ID: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    DunningLetterRequestId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )

    IPR: Mapped[str] = mapped_column(String(26))
    OpenTextIPR: Mapped[str] = mapped_column(String(255))
    RunId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    FileName: Mapped[str] = mapped_column(String(255))
    RequestDateTime: Mapped[datetime] = mapped_column(DateTime)
    DunningReminderLevel: Mapped[int] = mapped_column(nullable=False)  # 1, 2, or 3
    DunningCycleCode: Mapped[str] = mapped_column(String(10), nullable=True)

    OpenTextTrackerId: Mapped[str] = mapped_column(Text, nullable=True)
    RequestSubmissionStatus: Mapped[str] = mapped_column(String(26), nullable=True)
    PdfGenerationStatus: Mapped[str] = mapped_column(String(26), nullable=True)
    RequestBody: Mapped[str] = mapped_column(Text, nullable=True)
    PdfContent: Mapped[str] = mapped_column(Text, nullable=True)
    ProcessingStatus: Mapped[str] = mapped_column(Text, nullable=True)
    ReasonForFailure: Mapped[str] = mapped_column(Text, nullable=True)
