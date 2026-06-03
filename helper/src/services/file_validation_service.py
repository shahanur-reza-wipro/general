from datetime import datetime

from services.handlers.file_validation_info import FileValidationInfo
from services.handlers.file_validator import FileValidator
from utilities.coniguration import Configuration
from .file_service import FileService
from .notification_service import NotificationService
from repositories import RunControlRepository, RunBatchRepository
from utilities import Utility
import logging

log = logging.getLogger()


class FileValidationService:

    DEBTOR_FILE_VALIDATION_LOGGER = "DebtorFileValidator"
    TRANSACTION_FILE_VALIDATION_LOGGER = "TransactionFileValidator"

    def __init__(self):
        configuration = Configuration().get_config()
        self.notification_service = NotificationService()
        self.run_control_repository = RunControlRepository()
        self.run_batch_repository = RunBatchRepository()
        self.file_service = FileService()
        self.file_validator = FileValidator(configuration.fileValidationConditions)

    def validate_debtor_file(self, file_object, file_name):
        is_valid_file, run_control_id = self.validate_file(
            "Debtor",
            file_object,
            file_name,
            FileValidationService.DEBTOR_FILE_VALIDATION_LOGGER,
        )

        log.info(
            f"validate_debtor_file was called and file {file_name} validated and status: {is_valid_file}"
        )

        self.update_run_batch_for_file_validation("Debtor")

        return is_valid_file, run_control_id

    def update_run_batch_for_file_validation(self, file_type):
        run_batches = self.run_batch_repository.get_all()
        if run_batches:
            run_batch = run_batches[0]
            if file_type == "Debtor":
                run_batch.HasDebtorFileValidated = True
            if file_type == "Transaction":
                run_batch.HasTransactionFileValidated = True

            self.run_batch_repository.upsert(run_batch)

    def validate_transaction_file(self, file_object, file_name):
        is_valid_file, run_control_id = self.validate_file(
            "Transaction",
            file_object,
            file_name,
            FileValidationService.TRANSACTION_FILE_VALIDATION_LOGGER,
        )

        self.update_run_batch_for_file_validation("Transaction")

        return is_valid_file, run_control_id

    def validate_file(self, model_name, file_object, file_name, validation_logger):

        model = self.file_service.get_record(file_object, model_name, 1)

        file_validation_info = FileValidationInfo(
            filename=file_name,
            application_date=Utility.convert_to_date(model.get("ApplicationDate")) if model else None,
            extract_date=Utility.convert_to_date(model.get("ExtractDate")) if model else None,
            model_name=model_name,
            first_record_end_field=model.get("EndField") if model else None,
            first_record_raw_line=model.get("_raw_line") if model else None,
            first_record_raw_line_length=model.get("_raw_line_length") if model else None,
        )

        is_valid_file = self.file_validator.validate(
            file_validation_info, validation_logger
        )

        run_controls = self.run_control_repository.get_run_control_by_received_date_and_file_name(
            datetime.today().date(), file_name
        )

        if run_controls:
            run_control = run_controls[0]

            run_control.IsValidDebtorFile = (
                is_valid_file
                if model_name == "Debtor"
                else run_control.IsValidDebtorFile
            )

            run_control.IsValidTransactionFile = (
                is_valid_file
                if model_name == "Transaction"
                else run_control.IsValidTransactionFile
            )

            run_control.ApplicationDate = file_validation_info.application_date
            run_control.ExtractDate = file_validation_info.extract_date

            run_control = self.run_control_repository.upsert(run_control)

            return is_valid_file, run_control.ID

        return False, None