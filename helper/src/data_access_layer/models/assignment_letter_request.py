from dataclasses import dataclass
import uuid
from sqlalchemy import UUID, Date, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .model import ModelBase


@dataclass
class AssignmentLetterRequest(ModelBase):
    """AssignmentLetterRequest model – stores batched OpenText submission requests."""

    __tablename__ = "assignment_letter_request"

    AssignmentLetterRequestID: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
    )

    RequestDate: Mapped[Date] = mapped_column(Date)
    ExpectedLetterCount: Mapped[int] = mapped_column(Numeric(10))

    SubmissionStatus: Mapped[str] = mapped_column(String(26), nullable=True)
    SubmissionResult: Mapped[str] = mapped_column(Text, nullable=True)
    RequestBase64Body: Mapped[str] = mapped_column(Text, nullable=True)

    SubmissionId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
