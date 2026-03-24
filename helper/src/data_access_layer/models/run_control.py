from dataclasses import dataclass
import json
import uuid
from typing import List

from sqlalchemy import DateTime, String, UUID, Date, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .model import ModelBase
from datetime import datetime


@dataclass
class RunControl(ModelBase):
    """RunControl model that inherits from ModelBase"""

    __tablename__ = "run_control"

    ID: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    DebtorRunDateTime: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    DebtorFileName: Mapped[str] = mapped_column(String(255), nullable=True)
    TransactionFileName: Mapped[str] = mapped_column(String(255), nullable=True)
    TransactionRunDateTime: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    ApplicationDate: Mapped[Date] = mapped_column(Date, nullable=True)
    ExtractDate: Mapped[Date] = mapped_column(Date, nullable=True)
    ReceivedDate: Mapped[Date] = mapped_column(Date, nullable=True)

    IsValidTransactionFile: Mapped[bool] = mapped_column(Boolean, nullable=True)
    IsValidDebtorFile: Mapped[bool] = mapped_column(Boolean, nullable=True)

    HasDebtorFileProcessed: Mapped[bool] = mapped_column(Boolean, nullable=True)
    HasTransactionFileProcessed: Mapped[bool] = mapped_column(Boolean, nullable=True)
    HasFileReceiptNotified: Mapped[bool] = mapped_column(Boolean, nullable=True)
    HasFilesProcessedNotified: Mapped[bool] = mapped_column(Boolean, nullable=True)

    Debtors: Mapped[List["Debtor"]] = relationship(
        "Debtor",
        primaryjoin="Debtor.RunId == RunControl.ID",
        foreign_keys="[Debtor.RunId]",
        viewonly=True,
        back_populates="RunControl",
    )

    Transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction",
        primaryjoin="Transaction.RunId == RunControl.ID",
        foreign_keys="[Transaction.RunId]",
        viewonly=True,
        back_populates="RunControl",
    )

    def to_json(self):
        run_control_dict = {
            "ID": str(self.ID),
            "DebtorRunDateTime": (
                self.DebtorRunDateTime.isoformat() if self.DebtorRunDateTime else None
            ),
            "DebtorFileName": self.DebtorFileName,
            "TransactionFileName": self.TransactionFileName,
            "TransactionRunDateTime": (
                self.TransactionRunDateTime.isoformat()
                if self.TransactionRunDateTime
                else None
            ),
            "ApplicationDate": (
                self.ApplicationDate.isoformat() if self.ApplicationDate else None
            ),
            "ExtractDate": (
                self.ExtractDate.isoformat() if self.ExtractDate else None
            ),
            "ReceivedDate": (
                self.ReceivedDate.isoformat() if self.ReceivedDate else None
            ),
            "IsValidTransactionFile": self.IsValidTransactionFile,
            "IsValidDebtorFile": self.IsValidDebtorFile,
            "HasDebtorFileProcessed": self.HasDebtorFileProcessed,
            "HasTransactionFileProcessed": self.HasTransactionFileProcessed,
            "HasFileReceiptNotified": self.HasFileReceiptNotified,
        }
        return run_control_dict