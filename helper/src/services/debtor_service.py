# debtor_service.py
from typing import List
from datetime import datetime
import logging

from data_access_layer.models.debtor import Debtor
from repositories import DebtorRepository, RunControlRepository
from services.file_processed_service import FileProcessedService
from utilities import Utility
from .file_validation_service import FileValidationService
from .record_validation_service import RecordValidationService
from .file_service import FileService
from .file_receipt_service import FileReceiptService


log = logging.getLogger()


class DebtorService:

    def __init__(self):
        self.file_service = FileService()
        self.record_validation_service = RecordValidationService()
        self.debtor_repository = DebtorRepository()
        self.run_control_repository = RunControlRepository()
        self.file_processed_service = FileProcessedService()
        self.invalid_iprs = []

    def process_debtors(self, file_object, file_name) -> List[Debtor]:

        print("Starting debtors ingestion")

        validated_debtors = []
        result = None

        is_valid_file, run_id = FileValidationService().validate_debtor_file(
            file_object, file_name
        )

        if is_valid_file:

            debtor_records = FileService().get_records(file_object, "Debtor")

            # Validate and save Debtors
            debtors = self.get_debtors(debtor_records)

            validated_debtors, invalid_iprs = self.record_validation_service.validate_debtors(
                debtors, run_id, file_name
            )

            unique_validated_debtors = list(
                {debtor.IPR: debtor for debtor in reversed(validated_debtors)}.values()
            )

            for debtor in unique_validated_debtors:
                debtor.RunId = run_id

            # Delete all records from Debtor table
            self.debtor_repository.delete_all()

            log.info("Saving debtors to database")

            result = self.debtor_repository.upsert(unique_validated_debtors)

            if run_id:
                run_control = self.run_control_repository.get_by_id(run_id)
                if run_control:
                    run_control.HasDebtorFileProcessed = True
                    run_control.DebtorRunDateTime = datetime.now()
                    run_control_id = self.run_control_repository.upsert(run_control)
                    log.info(f"Debtor {file_name} has processed. run_id: {run_control_id}")

            log.info(f"Starting file processed notification for Debtor file: {file_name}")
            self.file_processed_service.notify(file_name)
            log.info(f"Finished file processed notification operation for Debtor file: {file_name}")
            return result

    def get_debtors(self, records):

        # Dynamically create Debtor object from the record dictionary
        debtors = []
        debtor_kwargs = {}

        for record in records:
            try:
                for value in record.items():
                    property_name = value[0]
                    data = value[1]
                    if property_name:
                        if property_name in ["CallsOptOut"]:
                            data = data == "Y"
                        if property_name in ["StmFlag"]:
                            data = data == "1"
                        if property_name in ["AssignmentDue"]:
                            data = data == "1"
                        
                        elif property_name in ["CustomerAccountBalance"]:
                            data = Utility.convert_to_float(data)
                        elif property_name in ["ApplicationDate", "ExtractDate"]:
                            data = Utility.convert_to_date(data)
                        debtor_kwargs[property_name] = data
            except Exception as e:
                print(f"record failed on debtor: {record['DebtorNumber']}")
            debtor_kwargs["IPR"] = (
                record["ClientNumber"]
                + "/"
                + record["ClientAgreementNumber"]
                + "/"
                + record["DebtorNumber"]
            )

            debtor = Debtor(**debtor_kwargs)
            debtors.append(debtor)

        return debtors