import uuid
from sqlalchemy import String, UUID
from sqlalchemy.orm import Mapped, mapped_column
from .model import ModelBase


class FileValidationRule(ModelBase):
    """FileValidationRule model that inherits from ModelBase"""

    __tablename__ = 'file_validation_rule'

    ID: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        unique=True,
        nullable=False,
        default=uuid.uuid4
    )

    Name: Mapped[str] = mapped_column(String(255))
    Description: Mapped[str] = mapped_column(String(255))