from dataclasses import dataclass
import uuid
from sqlalchemy import String, UUID, Boolean
from sqlalchemy.orm import Mapped, mapped_column
from .model import ModelBase


@dataclass
class RunBatch(ModelBase):
    """RunBatch model that inherits from ModelBase"""

    __tablename__ = "run_batch"

    ID: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    DebtorFileName: Mapped[str] = mapped_column(String(255), nullable=True)
    TransactionFileName: Mapped[str] = mapped_column(String(255), nullable=True)
    HasDebtorFileValidated: Mapped[bool] = mapped_column(
        Boolean, nullable=True, default=False
    )
    HasTransactionFileValidated: Mapped[bool] = mapped_column(
        Boolean, nullable=True, default=False
    )

    def to_json(self):
        run_control_dict = {
            "ID": str(self.ID),
            "DebtorFileName": self.DebtorFileName,
            "TransactionFileName": self.TransactionFileName,
            "HasDebtorFileValidated": self.HasDebtorFileValidated,
            "HasTransactionFileValidated": self.HasTransactionFileValidated,
        }
        return run_control_dict