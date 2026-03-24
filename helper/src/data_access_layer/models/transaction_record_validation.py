from datetime import datetime
import uuid

from sqlalchemy import DateTime, String, UUID, Text
from sqlalchemy.orm import Mapped, mapped_column
from .model import ModelBase


class TransactionRecordValidation(ModelBase):
    """TransactionRecordValidation model that inherits from ModelBase"""

    __tablename__ = "transaction_record_validation"

    ID: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        unique=True,
        nullable=False,
        default=uuid.uuid4
    )

    RunId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))

    IPR: Mapped[str] = mapped_column(String(26))

    ValidationDateTime: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False
    )

    Error: Mapped[str] = mapped_column(String(255))

    ConditionName: Mapped[str] = mapped_column(String(255))

    Description: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )

    FileName: Mapped[str] = mapped_column(String(255))