import asyncio
from services.handlers.record_validation_info import RecordValidationInfo
from services.handlers.record_validator import RecordValidator
from utilities.coniguration import Configuration


class RecordValidationService:
    DEBTOR_FILE_VALIDATION_LOGGER = "DebtorFileValidator"
    TRANSACTION_FILE_VALIDATION_LOGGER = "TransactionFileValidator"

    def __init__(self):
        configuration = Configuration().get_config()
        self.record_validator = RecordValidator(
            configuration.recordValidationConditions
        )

    def validate_debtors(self, debtors, run_id, file_name):
        validated_debtors, invalid_iprs = self.validate_records(
            debtors,
            run_id,
            file_name,
            RecordValidationInfo.DEBTOR_RECORD_VALIDATOR,
        )
        return validated_debtors, invalid_iprs

    def validate_transactions(self, transactions, run_id, file_name):
        validated_transactions, invalid_iprs = self.validate_records(
            transactions,
            run_id,
            file_name,
            RecordValidationInfo.TRANSACTION_RECORD_VALIDATOR,
        )
        return validated_transactions, invalid_iprs

    def validate_records(self, records, run_id, file_name, validation_logger):
        record_validation_info = RecordValidationInfo(
            run_id=run_id,
            filename=file_name,
        )

        validated_records, invalid_iprs = asyncio.run(
            self.record_validator.validate_records(
                records,
                record_validation_info,
                validation_logger,
            )
        )

        return validated_records, invalid_iprs