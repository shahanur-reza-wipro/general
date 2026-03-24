from dataclasses import dataclass
import uuid
from sqlalchemy import UUID, Date, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from .model import ModelBase


@dataclass
class StatementValidation(ModelBase):
    """StatementValidation model that inherits from ModelBase"""

    __tablename__ = "statement_validation"

    ID: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    IPR: Mapped[str] = mapped_column(String(26))
    ConditionName: Mapped[str] = mapped_column(String(255))
    Log: Mapped[str] = mapped_column(String(255))
    Description: Mapped[str] = mapped_column(Text, nullable=True)
    RunId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    FileName: Mapped[str] = mapped_column(String(255))
    StatementRequestDate: Mapped[Date] = mapped_column(Date)