# file_processed_service.py

from datetime import datetime
from zoneinfo import ZoneInfo
import logging

from services.statement_orchestration_service import StatementOrchestrationService
from services.assignment_letter_orchestration_service import AssignmentLetterOrchestrationService
from services.dunning_letter_orchestration_service import DunningLetterOrchestrationService
from services.files_processing_status_report_scheduler_service import FilesProcessingStatusReportSchedulerService
from utilities.coniguration import Configuration
from utilities.utility import Utility
from .notification_service import NotificationService
from repositories import (
    RunControlRepository,
    RunBatchRepository,
    DebtorFileValidationRepository,
    TransactionFileValidationRepository,
)


log = logging.getLogger()


class FileProcessedService:

    def __init__(self):
        self.notification_service = NotificationService()
        self.run_control_repository = RunControlRepository()
        self.run_batch_repository = RunBatchRepository()
        self.debtor_file_validation_repository = DebtorFileValidationRepository()
        self.transaction_file_validation_repository = TransactionFileValidationRepository()
        self.files_processing_status_report_scheduler_service = FilesProcessingStatusReportSchedulerService()

        self.configuration = Configuration()
        self.file_type = None
        self.hasFileProcessedPreviously = False

    def notify(self, file_name):
        if self.configuration.isLocal:
            log.info("Local mode enabled. Skipping file processed email notification.")

        # send email message via sns if both file processed
        notification_result = None
        current_date = datetime.today().date()

        run_batches = self.run_batch_repository.get_all()
        run_batch = None

        if run_batches:
            run_batch = run_batches[0]
            if run_batch:
                if (
                    run_batch.DebtorFileName
                    and run_batch.TransactionFileName
                    and run_batch.HasDebtorFileValidated
                    and run_batch.HasTransactionFileValidated
                ):
                    self.hasFileProcessedPreviously = True
                else:
                    return

        run_control = self.get_run_control(file_name)

        if run_control:
            if (
                run_control.DebtorFileName
                and run_control.TransactionFileName
                and (
                    run_control.HasFilesProcessedNotified is None
                    or run_control.HasFilesProcessedNotified is False
                )
                and (
                    run_control.IsValidDebtorFile is not None
                    and run_control.IsValidTransactionFile is not None
                )
            ) or self.hasFileProcessedPreviously:

                notification_result = self.send_notification(run_control)

                if not self.hasFileProcessedPreviously:
                    self.schedule_processing_status_report(run_control)
                    self.schedule_summary_report(run_control)

                if self.hasFileProcessedPreviously:
                    self.run_batch_repository.delete_all()
                    return

                if (
                    run_control.HasDebtorFileProcessed
                    and run_control.HasTransactionFileProcessed
                ):
                    if run_control.IsValidDebtorFile and run_control.IsValidTransactionFile:
                        # only if both files are valid
                        # queue Debtors for Statement Generation
                        statement_orchestration_service = StatementOrchestrationService()
                        log.info("starting to queue for statement generation validation")
                        list_of_queued_iprs = (
                            statement_orchestration_service.queue_to_validate_statement_generation()
                        )

                        # queue Debtors for Assignment Letter Generation (independent of statements)
                        if self.configuration.enableAssignmentLetters:
                            assignment_letter_orchestration_service = AssignmentLetterOrchestrationService()
                            log.info("starting to queue for assignment letter validation")
                            assignment_letter_orchestration_service.queue_to_validate_assignment_letter_generation()
                        else:
                            log.info("Assignment letter generation is disabled via config (enableAssignmentLetters=false).")

                        # queue Debtors for Dunning Letter Generation (independent of statements and assignment letters)
                        if self.configuration.enableDunningLetters:
                            dunning_letter_orchestration_service = DunningLetterOrchestrationService()
                            log.info("starting to queue for dunning letter validation")
                            dunning_letter_orchestration_service.queue_to_validate_dunning_letter_generation()
                        else:
                            log.info("Dunning letter generation is disabled via config (enableDunningLetters=false).")
                    else:
                        log.info(
                            f"both files are not valid. "
                            f"IsValidDebtorFile: {run_control.IsValidDebtorFile}, "
                            f"IsValidTransactionFile: {run_control.IsValidTransactionFile}"
                        )
                else:
                    log.info(
                        f"could not queue for statement generation validation, "
                        f"{run_control.HasDebtorFileProcessed}--{run_control.HasTransactionFileProcessed}"
                    )

        return notification_result

    def schedule_processing_status_report(self, run_control):
        if self.configuration.isLocal:
            log.info("Local mode enabled. Skipping EventBridge scheduling for processing status report.")
            return

        payload = {
            "submission_id": str(run_control.ID)
        }

        self.files_processing_status_report_scheduler_service.schedule_statement_status_report_generation(
            self.configuration.fileProcessedReportGeneratorLambdaDetailsSecretName,
            self.configuration.processingReportGenerationAttemptInterval,
            True,
            payload
        )

    def schedule_summary_report(self, run_control):
        if self.configuration.isLocal:
            log.info("Local mode enabled. Skipping EventBridge scheduling for summary report.")
            return

        payload = {
            "submission_id": str(run_control.ID)
        }

        self.files_processing_status_report_scheduler_service.schedule_statement_status_report_generation(
            self.configuration.fileSummaryReportGeneratorLambdaDetailsSecretName,
            self.configuration.summaryReportGenerationAttemptInterval,
            False,
            payload
        )

    def send_notification(self, run_control):
        debtor_file_validation_log = self.debtor_file_validation_repository.get_by_filename(
            run_control.DebtorFileName
        )

        transaction_file_validation_log = (
            self.transaction_file_validation_repository.get_by_filename(
                run_control.TransactionFileName
            )
        )

        template_args = {}
        now = datetime.now(ZoneInfo("Europe/London"))
        template_args["date"] = now.strftime("%d/%m/%Y")
        template_args["time"] = now.strftime("%H:%M")
        template_args["env"] = self.configuration.env
        template_args["name"] = (
            "FILE_PROCESSED"
            if not self.hasFileProcessedPreviously
            else "FILE_PROCESSED_PREVIOUSLY"
        )
        template_args["debtor_file_name"] = run_control.DebtorFileName
        template_args["transaction_file_name"] = run_control.TransactionFileName
        template_args["status"] = (
            "Processed Successfully"
            if run_control.IsValidDebtorFile
            and run_control.IsValidTransactionFile
            and not self.hasFileProcessedPreviously
            else "Processed Fail"
        )

        template_args["debtor_file_status"] = (
            "was processed successfully"
            if not debtor_file_validation_log
            else "failed to process with the following error: "
            + debtor_file_validation_log[0].Error
        )

        template_args["transaction_file_status"] = (
            "was processed successfully"
            if not transaction_file_validation_log
            else "failed to process with the following error: "
            + transaction_file_validation_log[0].Error
        )

        email_template_name = template_args["name"]

        result = (
            self.notification_service.send_email(template_args, email_template_name)
            if not self.configuration.isLocal
            else None
        )

        run_control.HasFilesProcessedNotified = True
        run_control = self.run_control_repository.upsert(run_control)
        return result

    def get_run_control(self, file_name):
        self.file_type = Utility.get_file_content_type(file_name)
        column_file_name, column_file_processed = (
            self.run_control_repository.COLUMN_MAPPER.get(self.file_type)
        )

        run_controls = self.run_control_repository.get_run_control_by_filename(
            file_name, column_file_name
        )

        if run_controls:
            return run_controls[0]

        return None