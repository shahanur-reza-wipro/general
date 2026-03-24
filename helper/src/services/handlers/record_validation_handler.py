from datetime import date, datetime
import json
from sqlalchemy import Boolean, Date, Numeric, String, inspect
from utilities import SchemaManager, RecordCondition, RecordConditions
from data_access_layer.models import DebtorRecordValidation, TransactionRecordValidation
from repositories import DebtorRecordValidationRepository, TransactionRecordValidationRepository

class RecordConditionGenerationHandler:
    RECORD_VALIDATION_LOGGER = {
        "DebtorRecordValidator": (DebtorRecordValidation, DebtorRecordValidationRepository, "Debtor"),
        "TransactionRecordValidator": (TransactionRecordValidation, TransactionRecordValidationRepository, "Transaction"),
    }

    def __init__(self, successor=None):
        self.successor = successor
        self.debtor_record_validation_repository = DebtorRecordValidationRepository()
        self.transaction_record_validation_repository = TransactionRecordValidationRepository()
        self.debtor_file_name_cache = {}
        self._record_conditions = None
        self._schema_manager = SchemaManager()

    @property
    def record_conditions(self):
        if self._record_conditions is None:
            self._record_conditions = RecordConditions()
        return self._record_conditions

    def handle(self, record, record_validation_info, validation_logger, invalid_json):
        if self.successor:
            return self.successor.handle(record, record_validation_info, validation_logger, invalid_json)
        return True

    def log_record_operation(self, record, record_validation_info, validation_logger, conn, error_msg) -> str:
        record_condition = RecordCondition(**conn)
        self.logging_model, self.logging_repository, self.model_name = self.RECORD_VALIDATION_LOGGER.get(validation_logger)
        self.logging_repository = self.logging_repository()
        log = self.logger_model(
            RunId=record_validation_info.run_id,
            IPR=str(record.IPR) if hasattr(record, "IPR") else None,
            ValidationDateTime=datetime.now(),
            Error=error_msg,
            ConditionName=record_condition.name,
            Description=record_condition.description,
            FileName=record_validation_info.filename
        )
        log_id = self.logging_repository.add(log)
        return str(log_id)

class CheckInvalidIPRHandler(RecordConditionGenerationHandler):
    def handle(self, record, record_validation_info, validation_logger, invalid_iprs):
        if '' in [record.ClientNumber, record.ClientAgreementNumber, record.DebtorNumber, record.AccountNumber]:
            record_condition = self.record_conditions.get_condition(RecordConditions.CHECK_INVALID_IPR)
            invalid_iprs.append(record.IPR)
            error_msg = f"{record_condition['logMessage']} at line {record.SeqId}: Invalid IPR {record.IPR}."
            super().log_record_operation(record, record_validation_info, validation_logger, record_condition, error_msg)
            return False
        return super().handle(record, record_validation_info, validation_logger, invalid_iprs)

class EndWithXHandler(RecordConditionGenerationHandler):
    def handle(self, record, record_validation_info, validation_logger, invalid_iprs):
        if record.EndField != 'X':
            record_condition = self.record_conditions.get_condition(RecordConditions.END_WITH_X)
            invalid_iprs.append(record.IPR)
            error_msg = f"{record_condition['logMessage']} at line {record.SeqId}: for EndField."
            super().log_record_operation(record, record_validation_info, validation_logger, record_condition, error_msg)
            return False
        return super().handle(record, record_validation_info, validation_logger, invalid_iprs)

class FieldFormatHandler(RecordConditionGenerationHandler):
    def handle(self, record, record_validation_info, validation_logger, invalid_iprs):
        invalid_fields = []
        model_class = type(record)
        mapper = inspect(model_class)
        for column in mapper.columns:
            property_name = column.name
            property_type = column.type
            value = getattr(record, property_name)
            if value is None and column.nullable:
                continue
            actual_type_name = type(value).__name__
            if isinstance(property_type, String):
                if not isinstance(value, str):
                    invalid_fields[property_name] = {"expected": "String", "actual": actual_type_name, "value": value}
            if isinstance(property_type, Date):
                if not isinstance(value, date):
                    invalid_fields[property_name] = {"expected": "Date", "actual": actual_type_name, "value": value}
            if isinstance(property_type, Boolean):
                if not isinstance(value, bool):
                    invalid_fields[property_name] = {"expected": "Boolean", "actual": actual_type_name, "value": value}
            if isinstance(property_type, Numeric):
                if not isinstance(value, (int, float)):
                    invalid_fields[property_name] = {"expected": "Numeric", "actual": actual_type_name, "value": value}
        if invalid_fields:
            invalid_iprs.append(record.IPR)
            record_condition = self.record_conditions.get_condition(RecordConditions.FIELD_FORMAT)
            error_msg = f"{record_condition['logMessage']} at line {record.SeqId} for {json.dumps(invalid_fields)}"
            super().log_record_operation(record, record_validation_info, validation_logger, record_condition, error_msg)
        return super().handle(record, record_validation_info, validation_logger, invalid_iprs)