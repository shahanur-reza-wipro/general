# assignment_letter_validation_repository.py
from datetime import date
from typing import List
from uuid import UUID

from sqlalchemy import func

from data_access_layer.models.assignment_letter_validation import AssignmentLetterValidation
from data_access_layer import Database
from .abstract_repository import AbstractRepository


class AssignmentLetterValidationRepository(AbstractRepository):

    def __init__(self):
        self.db = Database()

    def add(self, record: AssignmentLetterValidation) -> str:
        self.db.insert(record)

    def update(self, record: AssignmentLetterValidation) -> str:
        return str(record.ID)

    def delete(self, record_id: UUID):
        record = self.get_by_id(record_id)
        if record:
            self.db.delete(record)

    def get_by_id(self, record_id: UUID) -> AssignmentLetterValidation:
        return self.db.get_by_id(record_id, AssignmentLetterValidation)

    def get_all(self) -> list:
        return self.db.get_all(AssignmentLetterValidation)

    def upsert(
        self,
        data,
        excluded_columns: list = [],
        exclude_id=True,
        chunk_size=100,
    ):
        result = self.db.upsert(data, excluded_columns, exclude_id, chunk_size)
        return result

    def get_validations_by_date(self, validation_date: date):
        conditions = [
            lambda q: q.filter(
                func.date(AssignmentLetterValidation.ValidationDate) == validation_date
            )
        ]
        return self.db.get_with_condition(AssignmentLetterValidation, conditions)
