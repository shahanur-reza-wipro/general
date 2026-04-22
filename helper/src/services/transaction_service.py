from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List
from datetime import datetime

from services.file_processed_service import FileProcessedService
from utilities import Utility
from utilities.coniguration import Configuration
from data_access_layer.models.run_control import RunControl
from data_access_layer import Transaction
from repositories import TransactionRepository, RunControlRepository
from .file_receipt_service import FileReceiptService
from .file_validation_service import FileValidationService
from .file_service import FileService
from .record_validation_service import RecordValidationService

import logging

log = logging.getLogger()


class TransactionService:

    def __init__(self):
        self.configuration = Configuration().get_config()
        self.file_service = FileService()
        self.transaction_repository = TransactionRepository()
        self.run_control_repository = RunControlRepository()
        self.record_validation_service = RecordValidationService()
        self.file_processed_service = FileProcessedService()

    def _get_or_create_local_run_control(self, file_name):
        run_controls = self.run_control_repository.get_run_control_by_received_date(
            datetime.today().date()
        )

        run_control = run_controls[0] if run_controls else RunControl()
        run_control.ReceivedDate = datetime.today().date()
        run_control.TransactionFileName = file_name
        run_control.IsValidTransactionFile = True
        run_control.HasTransactionFileProcessed = False
        run_control = self.run_control_repository.upsert(run_control)
        return run_control.ID

    def process_transactions(self, file_object, file_name) -> List[Transaction]:
        log.info("starting transactions ingestion")
        # notification_result = self.file_receipt_service.notify(file_name)
        validated_transactions = []

        # Validate Transaction file
        upsert_result = None
        if self.configuration.isLocal:
            is_valid_file = True
            run_id = self._get_or_create_local_run_control(file_name)
        else:
            is_valid_file, run_id = FileValidationService().validate_transaction_file(
                file_object, file_name
            )

        if is_valid_file:
            transaction_records = FileService().get_records(file_object, "Transaction")
            # validate and save transactions
            transactions = self.get_transactions(transaction_records, run_id)
            if self.configuration.isLocal:
                validated_transactions = transactions
                invalid_iprs = []
            else:
                validated_transactions, invalid_iprs = self.record_validation_service.validate_transactions(
                    transactions, run_id, file_name
                )
            validated_transactions.sort(
                key=lambda transaction: transaction.IPR if transaction is not None else ""
            )
            validated_transactions = [
                transaction for transaction in validated_transactions if transaction is not None
            ]
            # Delete all records from Transaction table
            self.transaction_repository.delete_all()
            log.info("Saving transactions to database")
            upsert_result = self.transaction_repository.upsert(validated_transactions)

        if run_id:
            run_control = self.run_control_repository.get_by_id(run_id)
            if run_control:
                run_control.HasTransactionFileProcessed = True
                run_control.TransactionRunDateTime = datetime.now()
                run_control_id = self.run_control_repository.upsert(run_control)
                log.info(
                    f"Transaction {file_name} has processed. run_id: {run_control_id}"
                )

        if self.file_processed_service is not None:
            log.info(
                f"Starting file processed notification for Transaction file: {file_name}"
            )
            self.file_processed_service.notify(file_name)
            log.info(
                f"Finished file processed notification operation for Transaction file: {file_name}"
            )
        return upsert_result

    def get_transactions(self, records, run_id, max_workers=4):
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            chunked_records = Utility.chunk_data(records)
            transactions = []
            tasks = [
                executor.submit(self.get_chunked_transactions, records, run_id)
                for records in chunked_records
            ]
            for task in as_completed(tasks):
                try:
                    trans = task.result()
                    transactions.extend(trans)
                except Exception as e:
                    raise
            return transactions

    def get_transaction(self, file_object):
        record = self.file_service.get_record(file_object, "Transaction", 1)
        transactions = self.get_chunked_transactions([record])
        return transactions[0]

    def get_chunked_transactions(self, records, run_id=None):
        # Dynamically create Transaction object from the record dictionary
        transactions = []
        transaction_dict = {}
        for record in records:
            for value in record.items():
                property_name = value[0]
                data = value[1]
                if property_name and not property_name.startswith("_"):
                    if property_name in ["Disputed", "Overdue"]:
                        data = data == "Y"
                    elif property_name in ["ItemBalance", "ItemAmount"]:
                        data = Utility.convert_to_float(data)
                    elif property_name in ["DueDate", "DocumentDate", "ApplicationDate", "ExtractDate"]:
                        data = Utility.convert_to_date(data)
                    transaction_dict[property_name] = data

            transaction_dict["IPR"] = (
                record["ClientNumber"]
                + "/"
                + record["ClientAgreementNumber"]
                + "/"
                + record["DebtorNumber"]
            )
            transaction_dict["RunId"] = run_id
            transaction = Transaction(**transaction_dict)
            transaction._raw_line = record.get("_raw_line")
            transaction._raw_line_length = record.get("_raw_line_length")
            transactions.append(transaction)

        return transactions