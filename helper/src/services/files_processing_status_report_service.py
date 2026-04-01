from datetime import datetime, date
from collections import defaultdict
from zoneinfo import ZoneInfo
import logging

from repositories import (
    TransactionRecordValidationRepository,
    StatementValidationRepository,
    AssignmentLetterValidationRepository,
    DunningLetterValidationRepository,
    DebtorRecordValidationRepository,
    StatementRepository,
    AssignmentLetterRepository,
    DunningLetterRepository,
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
        self.assignment_letter_validation_repository = AssignmentLetterValidationRepository()
        self.dunning_letter_validation_repository = DunningLetterValidationRepository()
        self.statement_repository = StatementRepository()
        self.assignment_letter_repository = AssignmentLetterRepository()
        self.dunning_letter_repository = DunningLetterRepository()
        self.notification_service = NotificationService()
        self.debtor_repository = DebtorRepository()

        self.file_processing_status_report_scheduler_service = FilesProcessingStatusReportSchedulerService()

        self.statement_requests_sqs_helper = SQSHelper(
            self.configuration.requestsQueueName,
            self.configuration.integrationConfigSecretName
        )
        self.assignment_requests_sqs_helper = SQSHelper(
            self.configuration.assignmentLetterRequestsQueueName,
            self.configuration.integrationConfigSecretName,
        )
        self.dunning_requests_sqs_helper = SQSHelper(
            self.configuration.dunningLetterRequestsQueueName,
            self.configuration.integrationConfigSecretName,
        )

        self.submission_id = ""

    def send_report(self, submission_id):

        self.submission_id = submission_id

        pending_messages = self.get_total_pending_request_messages()
        still_pending = [doc_type for doc_type, count in pending_messages.items() if count > 0]

        if still_pending:
            log.info(f"System is still processing requests: {pending_messages}")
            return f"System is still processing requests for: {', '.join(still_pending)}."

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
            "Assignment Requested",
            "Dunning Requested",
            "Statement Requested",
            "Note Assignments",
            "Note Dunning",
            "Note Statements",
            "File Name",
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
        assignment_validations = self.fetch_data("assignment_validations")
        dunning_validations = self.fetch_data("dunning_validations")
        statements = self.fetch_data("statements")
        assignments = self.fetch_data("assignments")
        dunnings = self.fetch_data("dunnings")

        processing_statuses = []

        unique_iprs = self.get_unique_iprs(
            debtor_validations,
            transaction_validations,
            statement_validations,
            assignment_validations,
            dunning_validations,
            statements,
            assignments,
            dunnings,
        )

        iprs_map = self.create_map_of_ipr(
            debtor_validations,
            transaction_validations,
            statement_validations,
            assignment_validations,
            dunning_validations,
            statements,
            assignments,
            dunnings,
        )

        self.build_processing_statuses(processing_statuses, unique_iprs, iprs_map)

        processing_statuses = sorted(processing_statuses, key=lambda x: x["IPR"])

        return processing_statuses

    def fetch_data(self, type):

        validation_data = []

        today = date.today()

        func_map = {
            "debtor_validations": self.debtor_record_validation_repository.get_debtor_validations_by_date_with_pagination,
            "transaction_validations": self.transaction_record_validation_repository.get_transaction_validations_by_date_with_pagination,
            "statement_validations": self.statement_validation_repository.get_statement_validations_logs_by_date_with_pagination,
            "assignment_validations": self.assignment_letter_validation_repository.get_assignment_validations_logs_by_date_with_pagination,
            "dunning_validations": self.dunning_letter_validation_repository.get_dunning_validations_logs_by_date_with_pagination,
            "statements": self.statement_repository.get_statements_by_request_date_with_pagination,
            "assignments": self.assignment_letter_repository.get_assignment_letters_by_request_date_with_pagination,
            "dunnings": self.dunning_letter_repository.get_dunning_letters_by_request_date_with_pagination,
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

    def get_unique_iprs(self, debtor_validations, transaction_validations, statement_validations, assignment_validations, dunning_validations, statements, assignments, dunnings):

        unique_iprs = set()

        for lst in [
            debtor_validations,
            transaction_validations,
            statement_validations,
            assignment_validations,
            dunning_validations,
            statements,
            assignments,
            dunnings,
        ]:
            if lst:
                unique_iprs.update(item["IPR"] for item in lst if item is not None)

        return unique_iprs

    def build_processing_statuses(self, processing_statuses, unique_iprs, iprs_map):

        for ipr in unique_iprs:

            ipr_data = iprs_map.get(ipr)
            if not ipr_data:
                continue

            statement = ipr_data.get("statement")
            assignment = ipr_data.get("assignment")
            dunning = ipr_data.get("dunning")
            statement_validation = ipr_data.get("statement_validation")
            assignment_validation = ipr_data.get("assignment_validation")
            dunning_validation = ipr_data.get("dunning_validation")
            debtor_validation = ipr_data.get("debtor_validation")
            transaction_validation = ipr_data.get("transaction_validation")

            validation_data = (
                assignment_validation
                or dunning_validation
                or statement_validation
                or debtor_validation
                or transaction_validation
                or assignment
                or dunning
                or statement
            )

            file_name = validation_data["FileName"] if validation_data else None

            statement_notes = []
            assignment_notes = []
            dunning_notes = []

            if statement_validation:
                statement_notes.append(statement_validation["Log"])
            if debtor_validation:
                statement_notes.append(debtor_validation["Error"])
            if transaction_validation:
                statement_notes.append(transaction_validation["Error"])
            if assignment_validation:
                assignment_notes.append(assignment_validation["Log"])
            if dunning_validation:
                dunning_notes.append(dunning_validation["Log"])

            processing_status = {
                "IPR": ipr.replace("/", ""),
                "Assignment Requested": "Y" if assignment else "N",
                "Dunning Requested": "Y" if dunning else "N",
                "Statement Requested": "Y" if statement else "N",
                "Note Assignments": "\n".join(assignment_notes) if assignment_notes else None,
                "Note Dunning": "\n".join(dunning_notes) if dunning_notes else None,
                "Note Statements": "\n".join(statement_notes) if statement_notes else None,
                "File Name": file_name,
            }

            processing_statuses.append(processing_status)

    def create_map_of_ipr(self, debtor_validations, transaction_validations, statement_validations, assignment_validations, dunning_validations, statements, assignments, dunnings):

        iprs_map = defaultdict(
            lambda: {
                "debtor_validation": None,
                "transaction_validation": None,
                "statement_validation": None,
                "assignment_validation": None,
                "dunning_validation": None,
                "statement": None,
                "assignment": None,
                "dunning": None,
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

        for item in assignment_validations:
            if item:
                iprs_map[item["IPR"]]["assignment_validation"] = item

        for item in dunning_validations:
            if item:
                iprs_map[item["IPR"]]["dunning_validation"] = item

        for item in statements:
            if item:
                iprs_map[item["IPR"]]["statement"] = item

        for item in assignments:
            if item:
                iprs_map[item["IPR"]]["assignment"] = item

        for item in dunnings:
            if item:
                iprs_map[item["IPR"]]["dunning"] = item

        return iprs_map

    def get_total_pending_request_messages(self):
        statement_pending = self.statement_requests_sqs_helper.get_sqs_message_count() or 0
        assignment_pending = self.assignment_requests_sqs_helper.get_sqs_message_count() or 0
        dunning_pending = self.dunning_requests_sqs_helper.get_sqs_message_count() or 0
        return {
            "statement": statement_pending,
            "assignment": assignment_pending,
            "dunning": dunning_pending,
        }