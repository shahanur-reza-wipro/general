# transaction_record_validation_repository.py
from typing import List, Union
from data_access_layer.models import TransactionRecordValidation
from data_access_layer import Database
from .abstract_repository import AbstractRepository
from uuid import UUID
from sqlalchemy.orm import sessionmaker, scoped_session
from datetime import date
from sqlalchemy import func


class TransactionRecordValidationRepository(AbstractRepository):

    def __init__(self):
        self.db = Database()

    def add(self, transaction_record_validation: TransactionRecordValidation) -> str:
        self.db.insert(transaction_record_validation)

    def update(self, transaction_record_validation: TransactionRecordValidation) -> str:
        transaction_record_validation = self.db.update(transaction_record_validation)
        return str(transaction_record_validation.ID)

    def delete(self, transaction_record_validation_id: UUID):
        transaction_record_validation = self.get_by_id(transaction_record_validation_id)
        if transaction_record_validation:
            self.db.delete(transaction_record_validation)

    def get_by_id(self, transaction_record_validation_id: UUID) -> TransactionRecordValidation:
        return self.db.get_by_id(
            transaction_record_validation_id,
            TransactionRecordValidation
        )

    def get_all(self) -> list:
        return self.db.get_all(TransactionRecordValidation)

    def upsert(self, transaction_record_validations) -> List[str]:
        result = self.db.upsert(
            transaction_record_validations,
            [],
            True,
            100
        )  # exclude_id = True for auto-generated primary_key
        return result

    def get_transaction_validations_by_date_with_pagination(
        self,
        validation_date: date,
        submission_id,
        page_number=1,
        page_size=500
    ):

        # implementing pagination
        offset = (page_number - 1) * page_size

        conditions = [
            lambda q: q.filter(
                func.date(TransactionRecordValidation.ValidationDateTime) == validation_date
            ),
            lambda q: q.filter(
                func.text(TransactionRecordValidation.RunId) == str(submission_id)
            )
        ]

        transaction_record_validations = self.db.get_with_condition(
            TransactionRecordValidation,
            conditions,
            orderby=(TransactionRecordValidation.IPR, "asc"),
            offset=offset,
            limit=page_size
        )

        transaction_record_validations = [
            {
                "IPR": trv.IPR,
                "Error": trv.Error,
                "FileName": trv.FileName
            }
            for trv in transaction_record_validations
        ]

        return transaction_record_validations