import json
import logging
import uuid
from datetime import date, datetime
from decimal import Decimal

from data_access_layer.models.dunning_letter import DunningLetter
from data_access_layer.models.dunning_letter_request import DunningLetterRequest
from repositories import DebtorRepository, DunningLetterRepository, DunningLetterRequestRepository
from services.handlers.dunning_letter_generation_handler import DunningLetterGenerationHandler
from utilities.coniguration import Configuration
from utilities.sqs_helper import SQSHelper
from utilities.utility import Utility

log = logging.getLogger(__name__)


class DunningLetterValidationService:
    """
    Consumes chunked IPR messages from the dunning letter orchestrator queue,
    evaluates all dunning letter conditions for each debtor, builds an XML
    request payload and queues it for OpenText submission.
    """

    DUNNING_CYCLE_DESCRIPTIONS = {
        "5200": "Soft Cycle",
        "5201": "Medium Cycle",
        "5202": "Hard Cycle",
    }

    def __init__(self):
        self.configuration = Configuration().get_config()
        self.handler_chain = (
            DunningLetterGenerationHandler()
            .build_chain(self.configuration.dunningLetterGenerationConditions)
        )

        self.request_queue_name = self.configuration.dunningLetterRequestsQueueName
        self.integration_config_secret_name = (
            self.configuration.integrationConfigSecretName
        )

        self.debtor_repository = DebtorRepository()
        self.dunning_letter_repository = DunningLetterRepository()
        self.dunning_letter_request_repository = DunningLetterRequestRepository()

        self.is_last_chunk = False
        self.submission_id = None

    def validate(self, queued_debtors: list):
        log.info(
            f"Starting dunning letter validation for {len(queued_debtors)} debtors"
        )

        self.is_last_chunk = any(d.get("is_last_chunk") for d in queued_debtors)
        self.submission_id = queued_debtors[0].get("run_id") if queued_debtors else None

        iprs = [d["IPR"] for d in queued_debtors]
        debtors = self.debtor_repository.get_debtors_by_iprs(iprs) if iprs else []

        request_id, expected_count = self._process_debtors(debtors)

        if request_id:
            self._queue_request(request_id)
            return request_id

        return None

    def _process_debtors(self, debtors):
        request_id = uuid.uuid4()
        letters = []
        approved_debtors = []

        for debtor in debtors:
            conditions_met = self._check_conditions(debtor)

            if conditions_met:
                approved_debtors.append(debtor)
                letter = self._build_dunning_letter(request_id, debtor)
                if letter:
                    letters.append(letter)

        if letters:
            existing_request_count = self.dunning_letter_request_repository.get_total_request_submission(
                self.submission_id
            )
            total_requests = (
                existing_request_count + 1
                if existing_request_count == 0
                else existing_request_count
            )
            request_base64_body = self._build_request_xml(request_id, approved_debtors, total_requests)

            for letter in letters:
                letter.RequestBody = request_base64_body

            self.dunning_letter_repository.upsert(letters)
            self._persist_request(request_id, len(letters), request_base64_body)
            return request_id, len(letters)

        return None, 0

    def _check_conditions(self, debtor) -> bool:
        return bool(self.handler_chain.handle(debtor))

    def _build_dunning_letter(self, request_id, debtor) -> DunningLetter:
        try:
            reminder_level = int(str(getattr(debtor, "DunningReminder", 0) or 0))
            letter = DunningLetter(
                DunningLetterRequestId=request_id,
                IPR=debtor.IPR,
                OpenTextIPR=debtor.IPR.replace("/", "_"),
                RunId=debtor.RunId,
                FileName=debtor.RunControl.DebtorFileName,
                RequestDateTime=datetime.now(),
                DunningReminderLevel=reminder_level,
                DunningCycleCode=debtor.DunningCycleCode or "",
                RequestBody=None,
            )
            return letter
        except Exception as e:
            log.error(f"Failed to build dunning letter for debtor {debtor.IPR}: {e}")
            raise

    def _build_request_xml(self, request_id, debtors, total_requests) -> str:
        invoice_roots = []

        for debtor in debtors:
            debtor_email = debtor.DebtorStmEmail if debtor.DebtorStmEmail else ""
            dunning_reminder = str(getattr(debtor, "DunningReminder", "") or "")
            invoice_roots.append(
                {
                    "metadata": {
                        "isLastFile": "true" if self.is_last_chunk else "false",
                        "totalRequests": str(total_requests),
                        "submissionId": str(self.submission_id or ""),
                        "statementRequestId": str(request_id),
                        "generationDate": datetime.today().strftime("%Y-%m-%d"),
                        "printDestination": "EML" if debtor_email else "ARCH1",
                        "letterType": "DunningLetter",
                        "email": debtor_email,
                        "dunningReminder": dunning_reminder,
                    },
                    "invoice": self._build_invoice_node(debtor),
                }
            )

        payload = {
            "invoiceFinanceDunningDocumentRoot": invoice_roots,
        }

        xml_str = Utility.dict_to_xml("invoices", payload)
        return Utility.encode_to_base64(xml_str)

    def _build_invoice_node(self, debtor):
        sorted_transactions = sorted(
            debtor.Transactions or [],
            key=lambda tran: (tran.ItemNumber, tran.SeqId),
        )

        transaction_rows = []
        running_balance = Decimal("0")
        total_balance = Decimal("0")
        overdue_balance = Decimal("0")
        last_due_date = None

        for tran in sorted_transactions:
            item_balance = Decimal(str(tran.ItemBalance or 0))
            running_balance += item_balance
            total_balance += item_balance

            if tran.Overdue:
                overdue_balance += item_balance

            if tran.DueDate:
                last_due_date = tran.DueDate

            transaction_rows.append(
                {
                    "docDate": tran.DocumentDate.strftime("%Y-%m-%d")
                    if not Utility.is_none_or_empty(tran.DocumentDate)
                    else "",
                    "transType": tran.TransactionType or "",
                    "docRef": tran.DocumentReference or "",
                    "orderRef": tran.OrderReference or "",
                    "itemBalanceAmt": self._format_decimal(item_balance),
                    "dueDate": tran.DueDate.strftime("%Y-%m-%d")
                    if not Utility.is_none_or_empty(tran.DueDate)
                    else "",
                    "accountBalanceAmt": self._format_decimal(running_balance),
                    "od": self._map_od_flag(tran.Overdue, tran.Disputed),
                }
            )

        as_of_date = (
            last_due_date.strftime("%Y-%m-%d")
            if last_due_date
            else (
                debtor.ExtractDate.strftime("%Y-%m-%d")
                if not Utility.is_none_or_empty(debtor.ExtractDate)
                else date.today().strftime("%Y-%m-%d")
            )
        )

        return {
            "ipr": debtor.IPR,
            "debtorDetails": {
                "name": debtor.DebtorName or "",
                "addressLine1": debtor.DebtorAddr1 or "",
                "addressLine2": debtor.DebtorAddr2 or "",
                "addressLine3": debtor.DebtorAddr3 or "",
                "city": debtor.DebtorCity or "",
                "postCode": debtor.DebtorPostCode or "",
                "countryCode": debtor.DebtorCountry or "",
                "email": debtor.DebtorStmEmail or "",
            },
            "transactionDetails": {
                "transaction": transaction_rows,
            },
            "accountSummary": {
                "accountCurrency": debtor.AccountCurrency or "",
                "totalBalanceAmt": self._format_decimal(total_balance),
                "overdueAmt": self._format_decimal(overdue_balance),
                "asOfDate": as_of_date,
                "isOverdue": "true" if overdue_balance > 0 else "false",
            },
            "paymentInfo": {
                "bankName": debtor.BankName or "",
                "bankAddress1": debtor.BankAddress1 or "",
                "bankAddress2": debtor.BankAddress2 or "",
                "bankAddress3": debtor.BankAddress3 or "",
                "bankCity": debtor.BankCity or "",
                "bankPostCode": debtor.BankPostcode or "",
                "sortCode": debtor.InpaymentBankCode or "",
                "iban": debtor.InpaymentIbanNumber or "",
            },
            "collections": {
                "collectionsEmail": "cbf.allocations@closebrothers.com",
                "collectionsAuditEmail": "cbf.collectionsaudit@closebrothers.com",
            },
        }

    def _format_decimal(self, value):
        return f"{Decimal(str(value or 0)):.2f}"

    def _map_od_flag(self, is_overdue, is_disputed):
        if is_overdue and is_disputed:
            return "D/O"
        if is_overdue:
            return "O"
        if is_disputed:
            return "D"
        return "0"

    def _persist_request(self, request_id, expected_count, request_base64_body):
        request = DunningLetterRequest()
        request.DunningLetterRequestID = request_id
        request.RequestDate = datetime.today().date()
        request.ExpectedLetterCount = expected_count
        request.RequestBase64Body = request_base64_body
        request.SubmissionId = (
            uuid.UUID(str(self.submission_id))
            if self.submission_id
            else None
        )
        self.dunning_letter_request_repository.upsert(request)

    def _queue_request(self, request_id):
        message = json.dumps({"request_id": str(request_id)})
        sqs_helper = SQSHelper(
            self.request_queue_name,
            self.integration_config_secret_name,
        )
        sqs_helper.send_message(message)
        log.info(f"Dunning letter request {request_id} queued for submission")
