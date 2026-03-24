from dataclasses import dataclass, field
from typing import List
from datetime import date

@dataclass
class MetaData:
    isLastFile: bool
    submissionId: str
    totalReqeust: int
    statementRequestId: str
    generationDate: date
    printDestination: str
    letterType: str

@dataclass
class DebtorDetails:
    name: str
    addressLine1: str
    addressLine2: str
    addressLine3: str
    city: str
    postCode: str
    countryCode: str
    email: str

@dataclass
class Transaction:
    docDate: date
    transType: str
    docRef: str
    orderRef: str
    itemBalanceAmt: float
    dudeDate: date
    accountBalanceAmt: float
    od: str

@dataclass
class TransactionDetails:
    transaction: List[Transaction]
    accountCurrency: str
    totalBalanceAmt: float
    overdueAmt: float

@dataclass
class InPaymentInfo:
    bankCode: str
    bankAccount: str
    iban: str

@dataclass
class Invoice:
    ipr: str
    creditController: str
    clientName: str
    extractDate: date
    DebtorDetails: DebtorDetails
    transactionDetails: TransactionDetails
    inPaymentInfo: InPaymentInfo

@dataclass
class InvoiceFinanceDocumentRoot:
    metaData: MetaData
    invoice: Invoice

@dataclass
class invoices:
    invoiceFinanceDocumentRoot: List[InvoiceFinanceDocumentRoot] = field(default_factory=list)