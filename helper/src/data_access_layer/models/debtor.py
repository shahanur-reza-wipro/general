from dataclasses import asdict, dataclass
import json
from typing import List
import uuid

from sqlalchemy import UUID, ForeignKey, Integer, String, Boolean, Numeric, Date
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .model import ModelBase


@dataclass
class Debtor(ModelBase):
    """Debtor model that inherits from ModelBase, with UUID primary key."""

    __tablename__ = "debtor"

    IPR: Mapped[str] = mapped_column(String(26), primary_key=True)
    SeqId: Mapped[int] = mapped_column(Integer, nullable=False)

    ClientNumber: Mapped[str] = mapped_column(String(7), nullable=False)
    ClientAgreementNumber: Mapped[str] = mapped_column(String(3), nullable=False)
    AgreementCurrency: Mapped[str] = mapped_column(String(3), nullable=False)

    DebtorNumber: Mapped[str] = mapped_column(String(10), nullable=False)
    AccountNumber: Mapped[str] = mapped_column(String(3), nullable=False)
    AccountCurrency: Mapped[str] = mapped_column(String(3), nullable=False)

    ClientName: Mapped[str] = mapped_column(String(70), nullable=False)
    DebtorName: Mapped[str] = mapped_column(String(70), nullable=False)

    DebtorAddr1: Mapped[str] = mapped_column(String(40), nullable=True)
    DebtorAddr2: Mapped[str] = mapped_column(String(40), nullable=True)
    DebtorAddr3: Mapped[str] = mapped_column(String(40), nullable=True)

    DebtorCity: Mapped[str] = mapped_column(String(40), nullable=True)
    DebtorPostCode: Mapped[str] = mapped_column(String(12), nullable=True)
    DebtorCountry: Mapped[str] = mapped_column(String(2), nullable=True)

    CreditController: Mapped[str] = mapped_column(String(40), nullable=True)

    InpaymentBankCode: Mapped[str] = mapped_column(String(8), nullable=True)
    InpaymentBankAccount: Mapped[str] = mapped_column(String(8), nullable=True)
    InpaymentIbanNumber: Mapped[str] = mapped_column(String(34), nullable=True)
    BankName: Mapped[str] = mapped_column(String(70), nullable=True)
    BankAddress1: Mapped[str] = mapped_column(String(50), nullable=True)
    BankAddress2: Mapped[str] = mapped_column(String(40), nullable=True)
    BankAddress3: Mapped[str] = mapped_column(String(40), nullable=True)
    BankCity: Mapped[str] = mapped_column(String(40), nullable=True)
    BankState: Mapped[str] = mapped_column(String(40), nullable=True)
    BankPostcode: Mapped[str] = mapped_column(String(12), nullable=True)
    AssignmentDue: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    DunningReminder: Mapped[str] = mapped_column(String(1), nullable=True)
    DunningCycleCode: Mapped[str] = mapped_column(String(4), nullable=True)

    DebtorContact: Mapped[str] = mapped_column(String(70), nullable=True)
    DebtorStmEmail: Mapped[str] = mapped_column(String(50), nullable=True)

    CallsOptOut: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    StmFlag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    StmRunDay: Mapped[str] = mapped_column(String(2), nullable=True)
    DebtorFax: Mapped[str] = mapped_column(String(20), nullable=True)

    CustomerAccountBalance: Mapped[float] = mapped_column(Numeric, nullable=True)

    ApplicationDate: Mapped[Date] = mapped_column(Date)
    ExtractDate: Mapped[Date] = mapped_column(Date)

    MigrationReference: Mapped[str] = mapped_column(String(30), nullable=True)
    EndField: Mapped[str] = mapped_column(String(1), nullable=True)

    RunId: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))

    RunControl: Mapped["RunControl"] = relationship(
        "RunControl",
        primaryjoin="Debtor.RunId == RunControl.ID",
        foreign_keys=RunId,
        viewonly=True,
        back_populates="Debtors",
    )

    Transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction",
        primaryjoin="Debtor.IPR == Transaction.IPR",
        foreign_keys="[Transaction.IPR]",
        viewonly=True,
        back_populates="Debtor",
    )

    def __repr__(self):
        return f"<Debtor(IPR={self.IPR}, ClientName={self.ClientName}, CustomerAccountBalance={self.CustomerAccountBalance})>"

    def to_json(self):
        debtor_dict = {
            "IPR": self.IPR,
            "ClientNumber": self.ClientNumber,
            "ClientAgreementNumber": self.ClientAgreementNumber,
            "AgreementCurrency": self.AgreementCurrency,
            "DebtorNumber": self.DebtorNumber,
            "AccountNumber": self.AccountNumber,
            "AccountCurrency": self.AccountCurrency,
            "ClientName": self.ClientName,
            "DebtorName": self.DebtorName,
            "DebtorAddr1": self.DebtorAddr1,
            "DebtorAddr2": self.DebtorAddr2,
            "DebtorAddr3": self.DebtorAddr3,
            "DebtorCity": self.DebtorCity,
            "DebtorPostCode": self.DebtorPostCode,
            "DebtorCountry": self.DebtorCountry,
            "CreditController": self.CreditController,
            "InpaymentBankCode": self.InpaymentBankCode,
            "InpaymentBankAccount": self.InpaymentBankAccount,
            "InpaymentIbanNumber": self.InpaymentIbanNumber,
            "BankName": self.BankName,
            "BankAddress1": self.BankAddress1,
            "BankAddress2": self.BankAddress2,
            "BankAddress3": self.BankAddress3,
            "BankCity": self.BankCity,
            "BankState": self.BankState,
            "BankPostcode": self.BankPostcode,
            "AssignmentDue": self.AssignmentDue,
            "DunningReminder": self.DunningReminder,
            "DunningCycleCode": self.DunningCycleCode,
        }

        return json.dumps(debtor_dict)
    
    def to_debtor(self,debtor_dictionary):
        d = Debtor(**debtor_dictionary)
        return d