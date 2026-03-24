# debtor_record_validation_repository.py

from typing import List
from data_access_layer.models import DebtorRecordValidation
from data_access_layer import Database
from .abstract_repository import AbstractRepository
from uuid import UUID
from sqlalchemy.orm import sessionmaker, scoped_session
from datetime import date
from sqlalchemy import func


class DebtorRecordValidationRepository(AbstractRepository):

    def __init__(self):
        self.db = Database()

    def add(self, debtor_record_validation: DebtorRecordValidation) -> str:
        self.db.insert(debtor_record_validation)

    def update(self, debtor_record_validation: DebtorRecordValidation) -> str:
        debtor_record_validation = self.db.update(debtor_record_validation)
        return str(debtor_record_validation.ID)

    def delete(self, debtor_record_validation_id: UUID):
        debtor_record_validation = self.get_by_id(debtor_record_validation_id)
        if debtor_record_validation:
            self.db.delete(debtor_record_validation)

    def get_by_id(self, debtor_record_validation_id: UUID) -> DebtorRecordValidation:
        return self.db.get_by_id(debtor_record_validation_id, DebtorRecordValidation)

    def get_all(self) -> list:
        return self.db.get_all(DebtorRecordValidation)

    def upsert(self, debtor_record_validations) -> List[str]:
        result = self.db.upsert(
            debtor_record_validations,
            [],
            True
        )  # exclude_id = True for auto-generated primary_key
        return result

    def upsert(
        self,
        debtor_record_validation: DebtorRecordValidation
    ) -> DebtorRecordValidation:
        result = self.db.upsert(
            debtor_record_validation,
            [],
            True
        )  # exclude_id = True for auto-generated primary_key
        return result

    def get_debtor_validations_by_date_with_pagination(
        self,
        validation_date: date,
        submission_id,
        page_number=1,
        page_size=500
    ):
        # Implementing pagination
        offset = (page_number - 1) * page_size

        conditions = [
            lambda q: q.filter(
                func.date(DebtorRecordValidation.ValidationDateTime) == validation_date
            ),
            lambda q: q.filter(
                func.text(DebtorRecordValidation.RunId) == str(submission_id)
            )
        ]

        debtor_record_validations = self.db.get_with_condition(
            DebtorRecordValidation,
            conditions,
            orderby=DebtorRecordValidation.IPR.asc(),
            offset=offset,
            limit=page_size
        )

        debtor_record_validations = [
            {
                "IPR": drv.IPR,
                "Error": drv.Error,
                "FileName": drv.FileName
            }
            for drv in debtor_record_validations
        ]

        return debtor_record_validations