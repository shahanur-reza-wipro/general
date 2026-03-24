from dataclasses import dataclass
import json
import uuid
from sqlalchemy import Boolean, Date, Integer, Numeric, ForeignKey, String, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .model import ModelBase


@dataclass
class Transaction(ModelBase):
    __tablename__ = "transaction"

    RunId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    IPR: Mapped[str] = mapped_column(String(26))
    TransactionId: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    SeqId: Mapped[Integer] = mapped_column(Integer, nullable=False)
    ClientNumber: Mapped[str] = mapped_column(String(7))
    ClientAgreementNumber: Mapped[str] = mapped_column(String(3))
    AgreementCurrency: Mapped[str] = mapped_column(String(3))
    AccountCurrency: Mapped[str] = mapped_column(String(3))
    DebtorNumber: Mapped[str] = mapped_column(String(10))
    AccountNumber: Mapped[str] = mapped_column(String(3))
    ItemNumber: Mapped[str] = mapped_column(String(8))
    DocumentDate: Mapped[Date] = mapped_column(Date)
    TransactionType: Mapped[str] = mapped_column(String(20))
    DocumentReference: Mapped[str] = mapped_column(String(15))
    OrderReference: Mapped[str] = mapped_column(String(15))
    DueDate: Mapped[Date] = mapped_column(Date, nullable=True)
    Disputed: Mapped[bool] = mapped_column(Boolean)
    Overdue: Mapped[bool] = mapped_column(Boolean)
    ItemBalance: Mapped[float] = mapped_column(Numeric)
    ApplicationDate: Mapped[Date] = mapped_column(Date)
    ExtractDate: Mapped[Date] = mapped_column(Date)
    MigrationReference: Mapped[str] = mapped_column(String(30))
    ItemAmount: Mapped[float] = mapped_column(Numeric, nullable=False)
    EndField: Mapped[str] = mapped_column(String(1))  # Fixed the type to String(1)

    RunControl: Mapped["RunControl"] = relationship(
        "RunControl",
        primaryjoin="Transaction.RunId == RunControl.ID",
        foreign_keys=RunId,
        viewonly=True,
        back_populates="Transactions",
    )

    Debtor: Mapped["Debtor"] = relationship(
        "Debtor",
        primaryjoin="Transaction.IPR == Debtor.IPR",
        foreign_keys=IPR,
        viewonly=True,
        back_populates="Transactions",
    )

    def __repr__(self):
        return (
            f"<Transaction(TransactionId={self.TransactionId}, "
            f"RunId={self.RunId}, Ipr={self.IPR}, ClientNumber={self.ClientNumber}, "
            f"ItemBalance={self.ItemBalance})>"
        )

    def to_json(self):
        transaction_dict = {
            "RunId": str(self.RunId),  # Convert UUID to string
            "IPR": self.IPR,
            "TransactionId": str(self.TransactionId),  # Convert UUID to string
            "SeqId": str(self.SeqId),  # Convert UUID to string
            "ClientNumber": self.ClientNumber,
            "ClientAgreementNumber": self.ClientAgreementNumber,
            "AgreementCurrency": self.AgreementCurrency,
            "AccountCurrency": self.AccountCurrency,
            "DebtorNumber": self.DebtorNumber,
            "AccountNumber": self.AccountNumber,
            "ItemNumber": self.ItemNumber,
            "DocumentDate": (
                self.DocumentDate.isoformat() if self.DocumentDate else None
            ),
            "TransactionType": self.TransactionType,
            "DocumentReference": self.DocumentReference,
            "OrderReference": self.OrderReference,
            "DueDate": self.DueDate.isoformat() if self.DueDate else None,
            "Disputed": self.Disputed,
            "Overdue": self.Overdue,
            "ItemBalance": (
                float(self.ItemBalance) if self.ItemBalance is not None else None
            ),
            "ApplicationDate": (
                self.ApplicationDate.isoformat() if self.ApplicationDate else None
            ),
            "ExtractDate": self.ExtractDate.isoformat() if self.ExtractDate else None,
            "MigrationReference": self.MigrationReference,
            "ItemAmount": (
                float(self.ItemAmount) if self.ItemAmount is not None else None
            ),
            "EndField": self.EndField,
        }
        return transaction_dict