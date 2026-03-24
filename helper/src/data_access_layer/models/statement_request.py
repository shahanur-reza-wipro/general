from dataclasses import dataclass
import uuid
from sqlalchemy import UUID, Date, Numeric, String, Text, Integer
from sqlalchemy.orm import Mapped, mapped_column
from .model import ModelBase


@dataclass
class StatementRequest(ModelBase):
    """StatementRequest model that inherits from ModelBase"""

    __tablename__ = "statement_request"

    StatementRequestID: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True
    )

    StatementRequestDate: Mapped[Date] = mapped_column(Date)

    ExpectedStatementCount: Mapped[int] = mapped_column(Numeric(10))

    SubmissionStatus: Mapped[str] = mapped_column(
        String(26),
        nullable=True
    )

    SubmissionResult: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )

    StatementBase64RequestBody: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )

    SubmissionId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=True
    )