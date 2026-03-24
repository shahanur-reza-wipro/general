from dataclasses import dataclass
from datetime import datetime
import uuid

from sqlalchemy import UUID, Boolean, Date, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .model import ModelBase


@dataclass
class Statement(ModelBase):
    """Statement model that inherits from ModelBase"""

    __tablename__ = "statement"

    ID: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    StatementRequestId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=True
    )

    IPR: Mapped[str] = mapped_column(String(26))
    OpenTextIPR: Mapped[str] = mapped_column(String(255))
    RunId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    FileName: Mapped[str] = mapped_column(String(255))
    StatementRequestDateTime: Mapped[datetime] = mapped_column(DateTime)
    OpenTextTrackerId: Mapped[str] = mapped_column(Text, nullable=True)
    RequestSubmissionStatus: Mapped[str] = mapped_column(String(26), nullable=True)
    PdfGenerationStatus: Mapped[str] = mapped_column(String(26), nullable=True)
    StatementRequestBody: Mapped[str] = mapped_column(Text)
    PdfContent: Mapped[str] = mapped_column(Text, nullable=True)
    StatementProcessingStatus: Mapped[str] = mapped_column(Text, nullable=True)
    ReasonForFailure: Mapped[str] = mapped_column(Text, nullable=True)