from datetime import datetime
import json
import logging
import uuid

from data_access_layer.models import Debtor, Statement, StatementRequest
from repositories import (
    DebtorRepository,
    RunControlRepository,
    StatementRepository,
    StatementValidationRepository,
    StatementRequestRepository
)

from services.handlers.statement_generation_handler import StatementGenerationHandler
from utilities import SQSHelper

from .popos import (
    DebtorDetails,
    Transaction,
    TransactionDetails,
    InPaymentInfo,
    Invoice,
    InvoiceFinanceDocumentRoot,
    MetaData,
    invoices
)

from utilities.coniguration import Configuration
from utilities.utility import Utility

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class StatementValidationService:

    def __init__(self):
        self.configuration = Configuration().get_config()

        self.handler_chain = (
            StatementGenerationHandler()
            .build_chain(self.configuration.statementGenerationCondition)
        )

        self.invoices = Invoices()

        self.request_queue_name = self.configuration.requestQueueName
        self.integrationConfigSecretName = self.configuration.integrationConfigSecretName

        self.debtor_repository = DebtorRepository()
        self.run_control_repository = RunControlRepository()
        self.statement_repository = StatementRepository()
        self.statement_validation_repository = StatementValidationRepository()
        self.statement_request_repository = StatementRequestRepository()

        self.is_last_chunk = False
        self.submission_id = None

    def validate(self, queued_debtors: list):

        logger.info(
            f"starting statement validation for {len(queued_debtors)} debtors"
        )

        iprs = [{"debtor": ipr["IPR"]} for ipr in queued_debtors]

        self.is_last_chunk = any(
            debtor.get("is_last_chunk") for debtor in queued_debtors
        )

        self.submission_id = (
            queued_debtors[0].get("run_id") if queued_debtors else None
        )

        debtors = (
            self.debtor_repository.get_debtors_by_iprs(iprs)
            if iprs else None
        )

        validation_result = self.validate_statements(debtors)

        if validation_result:
            base64request, request_id, expected_statement_count = validation_result

            statementRequest = StatementRequest()
            statementRequest.StatementRequestID = request_id
            statementRequest.StatementBase64RequestBody = base64request
            statementRequest.StatementRequestDate = datetime.now().isoformat()
            statementRequest.ExpectedStatementCount = expected_statement_count
            statementRequest.SubmissionID = self.submission_id

            self.statement_request_repository.upsert(statementRequest)

            self.queue_statement_generation_requests(request_id)

            return base64request, request_id

        return None

    def queue_statement_generation_requests(self, request_id):

        sqs_message_body = {
            "request_id": str(request_id)
        }

        self.send_to_sqs(json.dumps(sqs_message_body))

        logger.info(
            f"request: {request_id} has been queued for submission"
        )

    def send_to_sqs(self, message_body):

        sqs_helper = SQSHelper(
            self.request_queue_name,
            self.integrationConfigSecretName
        )

        queue_response = sqs_helper.send_message(message_body)

        return queue_response

    def validate_statements(self, debtors):

        request_id = uuid.uuid4()

        statements = []
        statement_validations = []
        expected_statement_count = 0

        for debtor in debtors:

            if not debtor.Transactions:
                logger.info(
                    f"No transaction found for debtor {debtor.IPR}"
                )
                logger.info(f"Debtor: {debtor.to_json()}")
                continue

            logger.info("Performing statement validation")

            validation_result = (
                self.check_statement_generation_conditions(debtor)
            )

            if validation_result:

                logger.info("Statement validation result found")

                has_met_all_conditions, statement_validation = validation_result

                if has_met_all_conditions:
                    statements.append(
                        self.generate_statement_request(request_id, debtor)
                    )

                if statement_validation:
                    statement_validations.append(statement_validation)

        if statement_validations:
            self.statement_validation_repository.upsert(
                statement_validations
            )

        if statements:
            self.statement_repository.upsert(statements)
            expected_statement_count = len(statements)

        if self.invoices.invoiceFinanceDocumentRoot:
            request = Utility.wrap_value_to_xml(self.invoices)
            base64request = Utility.encode_to_base64(request)

            return base64request, request_id, expected_statement_count

        return None, None, None

    def check_statement_generation_conditions(self, debtor):
        return self.handler_chain.handle(debtor)

    def generate_statement_request(self, request_id, debtor):

        if debtor is None:
            return None

        try:

            invoice_request = self.get_statement_request(
                debtor,
                request_id
            )

            if invoice_request:
                self.invoices.invoiceFinanceDocumentRoot.append(
                    invoice_request
                )

                statement = self.prepare_statement(
                    debtor,
                    True,
                    request_id,
                    Utility.serialize_to_xml(invoice_request)
                )

                return statement

        except Exception as e:
            logger.error(
                f"Failed to process and send for statement generation. "
                f"Debtor: {debtor.IPR}, Error: {e}"
            )
            raise

    def get_total_request_submission(self, submission_id):

        total_request_submitted = (
            self.statement_request_repository
            .get_total_request_submission(submission_id)
        )

        logger.info(
            f"total request submitted to opentext is: "
            f"{total_request_submitted}"
        )

        return total_request_submitted

    def get_statement_request(self, debtor: Debtor, statement_request_id):

        odd_map = {
            (False, False): "",
            (True, False): "O",
            (False, True): "D",
            (True, True): "D/O"
        }

        meta_data = MetaData(
            submissionId=debtor.RunId,
            isLastFile=self.is_last_chunk,
            totalRequest=self.get_total_request_submission(debtor.RunId),
            statementRequestId=str(statement_request_id),
            generationDate=datetime.today().strftime("%Y-%m-%d"),
            printDestination="EMAIL"
            if debtor.DebtorStmEmail else "ARCH1",
            letterType="DebtorStatement"
        )

        debtor_details = DebtorDetails(
            name=debtor.DebtorName,
            addressLine1=debtor.DebtorAddr1,
            addressLine2=debtor.DebtorAddr2,
            addressLine3=debtor.DebtorAddr3,
            city=debtor.DebtorCity,
            postcode=debtor.DebtorPostCode,
            countryCode=debtor.DebtorCountry,
            email=debtor.DebtorStmEmail
        )

        transaction_list = []
        total_balance_amount = 0
        overdue_balance = 0

        sorted_transactions = sorted(
            debtor.Transactions,
            key=lambda tran: (tran.ItemNumber, tran.SeqId)
        )

        account_balance = 0

        for tran in sorted_transactions:

            account_balance += tran.ItemBalance

            transaction = Transaction(
                docDate=tran.DocumentDate.strftime("%Y-%m-%d")
                if not Utility.is_none_or_empty(tran.DocumentDate)
                else "",
                transType=tran.TransactionType,
                docRef=tran.DocumentReference,
                orderRef=tran.OrderReference,
                itemBalanceAmt=tran.ItemBalance,
                dueDate=tran.DueDate.strftime("%Y-%m-%d")
                if not Utility.is_none_or_empty(tran.DueDate)
                else "",
                accountBalanceAmt=account_balance,
                odd_map=odd_map.get(
                    (tran.Overdue, tran.Disputed)
                )
            )

            total_balance_amount += tran.ItemBalance

            overdue_balance = (
                overdue_balance + tran.ItemBalance
                if tran.Overdue else overdue_balance
            )

            transaction_list.append(transaction)

        transactionDetails = TransactionDetails(
            transactions=transaction_list,
            accountCurrency=debtor.AccountCurrency,
            totalBalanceAmt=total_balance_amount,
            overdueAmt=overdue_balance
        )

        in_payment_info = InPaymentInfo(
            bankCode=debtor.InpaymentBankCode,
            bankAccount=debtor.InpaymentBankAccount,
            iban=debtor.InpaymentIbanNumber
        )

        invoice = Invoice(
            ipr=debtor.IPR,
            creditController=debtor.CreditController,
            clientName=debtor.ClientName,
            extractDate=debtor.ExtractDate.strftime("%Y-%m-%d")
            if not Utility.is_none_or_empty(debtor.ExtractDate)
            else "",
            debtorDetails=debtor_details,
            transactionDetails=transactionDetails,
            inPaymentInfo=in_payment_info
        )

        invoice_finance_document_root = InvoiceFinanceDocumentRoot(
            metaData=meta_data,
            invoice=invoice
        )

        return invoice_finance_document_root

    def prepare_statement(
        self,
        debtor: Debtor,
        has_generated: bool,
        statement_request_id=None,
        statement_xml=None,
        open_text_response=None
    ):

        statement = Statement(
            StatementRequestId=str(statement_request_id),
            IPR=debtor.IPR,
            RunId=debtor.RunId,
            FileName=debtor.RunControl.DebtorFileName,
            OpenTextIPR=debtor.IPR.replace("/", "_"),
            StatementRequestDateTime=datetime.now(),
            StatementRequestBody=statement_xml
        )

        return statement