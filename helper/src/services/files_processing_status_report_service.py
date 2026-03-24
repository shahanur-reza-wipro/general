from datetime import datetime, date
from collections import defaultdict
from zoneinfo import ZoneInfo
import logging

from repositories import (
    TransactionRecordValidationRepository,
    StatementValidationRepository,
    DebtorRecordValidationRepository,
    StatementRepository,
    DebtorRepository
)

from .files_processing_status_report_scheduler_service import FilesProcessingStatusReportSchedulerService
from utilities import Utility, SQSHelper, Configuration
from .notification_service import NotificationService

log = logging.getLogger()
log.setLevel(logging.INFO)


class FilesProcessingStatusReportService:

    def __init__(self):
        self.configuration = Configuration().get_config()

        self.transaction_record_validation_repository = TransactionRecordValidationRepository()
        self.debtor_record_validation_repository = DebtorRecordValidationRepository()
        self.statement_validation_repository = StatementValidationRepository()
        self.statement_repository = StatementRepository()
        self.notification_service = NotificationService()
        self.debtor_repository = DebtorRepository()

        self.file_processing_status_report_scheduler_service = FilesProcessingStatusReportSchedulerService()

        self.sqs_helper = SQSHelper(
            self.configuration.requestsQueueName,
            self.configuration.integrationConfigSecretName
        )

        self.submission_id = ""

    def send_report(self, submission_id):

        self.submission_id = submission_id

        message_count = self.sqs_helper.get_sqs_message_count()

        if message_count and message_count > 0:
            log.info("System is still processing statement requests.")
            return "System is still processing statement requests."

        log.info("Starting to generate report.")
        report = self.get_report()

        if not report:
            log.info("could not generate report, deleting trigger for report scheduling.")
            rule_delete_result = self.file_processing_status_report_scheduler_service.delete_schedule_rule(
                self.configuration.integrationConfigSecretName,
                True
            )
            return

        template_args = {}

        now = datetime.now(ZoneInfo("Europe/London"))
        template_args["date"] = now.strftime("%d-%m-%Y")
        template_args["time"] = now.strftime("%H-%M")
        template_args["env"] = self.configuration.env

        filename = f"extract_files_processed_report{template_args['date']}_{template_args['time']}.csv"

        recipient_emails = self.configuration.fileProcessingReportRecipients

        notification_result = self.notification_service.send_email_with_attachment(
            template_args,
            "VALIDATION_DATA_REPORT",
            filename,
            report,
            recipient_emails
        )

        log.info("Deleting trigger for report scheduling.")
        rule_delete_result = self.file_processing_status_report_scheduler_service.delete_schedule_rule(
            self.configuration.integrationConfigSecretName,
            True
        )

        log.info(f"A report has been sent successfully to {recipient_emails}")
        return f"A report has been sent successfully to {recipient_emails}"

    def get_report(self):

        field_names = [
            "IPR",
            "Statement Requested",
            "Processing Note",
            "File Name",
            "Credit Controller",
            "Debtor Email Address"
        ]

        processing_statuses = self.get_processing_statuses()

        if processing_statuses:
            report = Utility.generate_csv(processing_statuses, field_names)
            return report

        return None

    def get_processing_statuses(self):

        today = date.today()

        debtor_validations = self.fetch_data("debtor_validations")
        transaction_validations = self.fetch_data("transaction_validations")
        statement_validations = self.fetch_data("statement_validations")
        statements = self.fetch_data("statements")

        processing_statuses = []

        unique_iprs = self.get_unique_iprs(
            debtor_validations,
            transaction_validations,
            statement_validations,
            statements
        )

        iprs_map = self.create_map_of_ipr(
            debtor_validations,
            transaction_validations,
            statement_validations,
            statements
        )

        unique_debtors = self.debtor_repository.get_debtor_repository_email(unique_iprs)

        iprs_map_debtor = {}

        for debtor in unique_debtors:
            ipr = debtor["IPR"]

            if ipr in iprs_map:
                iprs_map_debtor[ipr] = iprs_map[ipr]

                iprs_map_debtor[ipr]["credit_controller"] = debtor["CreditController"]
                iprs_map_debtor[ipr]["debtor_stn_email"] = debtor["DebtorStnEmail"]

        self.build_processing_statuses(processing_statuses, unique_iprs, iprs_map_debtor)

        processing_statuses = sorted(processing_statuses, key=lambda x: x["IPR"])

        return processing_statuses

    def fetch_data(self, type):

        validation_data = []

        today = date.today()

        func_map = {
            "debtor_validations": self.debtor_record_validation_repository.get_debtor_validations_by_date_with_pagination,
            "transaction_validations": self.transaction_record_validation_repository.get_transaction_validations_by_date_with_pagination,
            "statement_validations": self.statement_validation_repository.get_statement_validations_logs_by_date_with_pagination,
            "statements": self.statement_repository.get_statements_by_request_date_with_pagination
        }

        function = func_map[type]

        page_number = 1

        while True:

            records = function(
                today,
                self.submission_id,
                page_number=page_number,
                page_size=500
            )

            if not records:
                break

            validation_data.extend(records)

            page_number += 1

        return validation_data

    def get_unique_iprs(self, debtor_validations, transaction_validations, statement_validations, statements):

        unique_iprs = set()

        for lst in [debtor_validations, transaction_validations, statement_validations, statements]:
            if lst:
                unique_iprs.update(item["IPR"] for item in lst if item is not None)

        return unique_iprs

    def build_processing_statuses(self, processing_statuses, unique_iprs, iprs_map):

        for ipr in unique_iprs:

            ipr_data = iprs_map.get(ipr)

            statement = ipr_data.get("statement")
            statement_validation = ipr_data.get("statement_validation")
            debtor_validation = ipr_data.get("debtor_validation")
            transaction_validation = ipr_data.get("transaction_validation")

            credit_controller = ipr_data.get("credit_controller")
            debtor_stn_email = ipr_data.get("debtor_stn_email")

            validation_data = (
                statement_validation
                or debtor_validation
                or transaction_validation
                or statement
            )

            file_name = validation_data["FileName"] if validation_data else None

            notes = []

            if statement_validation:
                notes.append(statement_validation["Log"])

            if debtor_validation:
                notes.append(debtor_validation["Error"])

            if transaction_validation:
                notes.append(transaction_validation["Error"])

            processing_notes = "\n".join(notes) if notes else None

            processing_status = {
                "IPR": ipr.replace("/", ""),
                "Statement Requested": "N" if Utility.is_none_or_empty(statement["RequestSubmissionStatus"]) else statement["RequestSubmissionStatus"],
                "Processing Note": processing_notes,
                "File Name": file_name,
                "Credit Controller": credit_controller,
                "Debtor Email Address": debtor_stn_email
            }

            processing_statuses.append(processing_status)

    def create_map_of_ipr(self, debtor_validations, transaction_validations, statement_validations, statements):

        iprs_map = defaultdict(
            lambda: {
                "debtor_validation": None,
                "transaction_validation": None,
                "statement_validation": None,
                "statement": None
            }
        )

        for item in debtor_validations:
            if item:
                iprs_map[item["IPR"]]["debtor_validation"] = item

        for item in transaction_validations:
            if item:
                iprs_map[item["IPR"]]["transaction_validation"] = item

        for item in statement_validations:
            if item:
                iprs_map[item["IPR"]]["statement_validation"] = item

        for item in statements:
            if item:
                iprs_map[item["IPR"]]["statement"] = item

        return iprs_map