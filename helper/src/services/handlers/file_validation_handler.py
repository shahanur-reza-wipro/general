from datetime import datetime
from data_access_layer.models import DebtorFileValidation, TransactionFileValidation
from services.file_service import FileService
from services.handlers.file_validation_info import FileValidationInfo
from utilities import FileValidationConditions, FileValidationCondition, Utility
from repositories import RunControlRepository, DebtorFileValidationRepository, TransactionFileValidationRepository
from utilities import FixedLengthFileReader
from utilities import SchemaManager, Configuration


class FileValidationHandler:

    VALIDATION_LOGGER = {
        "DebtorFileValidator": (DebtorFileValidation, DebtorFileValidationRepository, "DebtorFileName", "HasDebtorFileProcessed"),
        "TransactionFileValidator": (TransactionFileValidation, TransactionFileValidationRepository, "TransactionFileName", "HasTransactionFileProcessed")
    }

    def __init__(self, successor=None):
        config = Configuration()
        self.configuration = config.get_config()
        self.successor = successor
        self.file_service = FileService()
        self.run_control_repository = RunControlRepository()
        self.file_name_cache = {}
        self._file_validation_conditions = None
        self.file_reader = FixedLengthFileReader()
        self.schema_manager = SchemaManager()

    @property
    def file_validation_conditions(self):
        if self._file_validation_conditions is None:
            self._file_validation_conditions = FileValidationConditions()
        return self._file_validation_conditions

    def handle(self, file_validation_info, validation_logger):
        if self.successor:
            return self.successor.handle(file_validation_info, validation_logger)
        return True

    def log_file_validation_operation(
            self, file_validation_info: FileValidationInfo, con: FileValidationCondition, validation_logger) -> str:

        condition = con if isinstance(con, FileValidationCondition) else FileValidationCondition(**con)
        self.logger_model, self.logger_repository, column_file_name, column_file_processed = self.VALIDATION_LOGGER.get(validation_logger)
        self.logging_repo = self.logger_repository()
        log = self.logger_model(
            ValidationDateTime=datetime.now(),
            Error=condition.logMessage,
            ConditionName=condition.name,
            FileName=file_validation_info.filename
        )

        log_id = self.logging_repo.add(log)
        return str(log_id)

    def compare_dates(self, file_date):
        file_date = Utility.normalize_date(file_date)
        if file_date is None:
            return False

        today_date = datetime.today().date()
        if file_date == today_date:
            is_matched = True
        else:
            is_matched = False
        return is_matched


class FilenameAndTypeHandler(FileValidationHandler):

    def handle(self, file_validation_info: FileValidationInfo, validation_logger):
        is_valid_file = self.file_service.validate_filetype(file_validation_info.filename)

        if not is_valid_file:
            file_validation_condition = self.file_validation_conditions.get_condition(
                FileValidationConditions.FILENAME_AND_FILETYPE
            )

            super().log_file_validation_operation(
                file_validation_info,
                file_validation_condition,
                validation_logger
            )
            return False

        return super().handle(file_validation_info, validation_logger)


class FileProcessedHandler(FileValidationHandler):

    def handle(self, file_validation_info: FileValidationInfo, validation_logger):

        self.logger_model, self.logger_repository, column_file_name, column_file_processed = self.VALIDATION_LOGGER.get(validation_logger)

        run_control = self.run_control_repository.get_run_control_by_filename_already_processed(
            file_validation_info.filename,
            column_file_name,
            column_file_processed
        )

        if run_control:
            file_validation_condition = self.file_validation_conditions.get_condition(
                FileValidationConditions.FILE_PROCESSED
            )

            super().log_file_validation_operation(
                file_validation_info,
                file_validation_condition,
                validation_logger
            )
            return False
        else:
            return super().handle(file_validation_info, validation_logger)


class FirstRecordEndsWithXHandler(FileValidationHandler):

    def handle(self, file_validation_info: FileValidationInfo, validation_logger):
        expected_end_position = Utility.get_end_field_position(
            file_validation_info.model_name,
            self.schema_manager,
        )
        raw_line = file_validation_info.first_record_raw_line
        raw_line_length = file_validation_info.first_record_raw_line_length
        end_field = (file_validation_info.first_record_end_field or "").strip()

        has_valid_end_value = end_field == "X"
        has_valid_end_position = False

        if expected_end_position is not None and raw_line_length is not None:
            has_valid_end_position = raw_line_length == expected_end_position

        if expected_end_position is not None and raw_line is not None:
            has_expected_char_position = len(raw_line) >= expected_end_position
            has_valid_end_position = (
                has_valid_end_position
                and has_expected_char_position
                and raw_line[expected_end_position - 1] == "X"
            )

        if not has_valid_end_value or not has_valid_end_position:
            file_validation_condition = self.file_validation_conditions.get_condition(
                FileValidationConditions.FIRST_RECORD_ENDS_WITH_X
            )
            super().log_file_validation_operation(
                file_validation_info,
                file_validation_condition,
                validation_logger
            )
            return False

        return super().handle(file_validation_info, validation_logger)
        
    
class ApplicationDateHandler(FileValidationHandler):

    def handle(self, file_validation_info: FileValidationInfo, validation_logger):

        applicationdate = file_validation_info.application_date
        if self.compare_dates(applicationdate):
            return super().handle(
                file_validation_info,
                validation_logger
            )
        else:
            file_validation_condition = self.file_validation_conditions.get_condition(
                FileValidationConditions.APPLICATION_DATE
            )
            super().log_file_validation_operation(
                file_validation_info,
                file_validation_condition,
                validation_logger
            )
            return False


class ExtractDateHandler(FileValidationHandler):

    def handle(self, file_validation_info: FileValidationInfo, validation_logger):
        extractdate = file_validation_info.extract_date
        if self.compare_dates(extractdate):
            return super().handle(
                file_validation_info,
                validation_logger
            )
        else:
            file_validation_condition = self.file_validation_conditions.get_condition(
                FileValidationConditions.EXTRACT_DATE
            )
            super().log_file_validation_operation(
                file_validation_info,
                file_validation_condition,
                validation_logger
            )
            return False