# dunning_letter_validation_repository.py
from datetime import date
from typing import List
from uuid import UUID

from sqlalchemy import func

from data_access_layer.models.dunning_letter_validation import DunningLetterValidation
from data_access_layer import Database
from .abstract_repository import AbstractRepository


class DunningLetterValidationRepository(AbstractRepository):

    def __init__(self):
        self.db = Database()

    def add(self, record: DunningLetterValidation) -> str:
        return self.db.insert(record)

    def update(self, record: DunningLetterValidation) -> str:
        record = self.db.update(record)
        return str(record.ID)

    def delete(self, record_id: UUID):
        record = self.get_by_id(record_id)
        if record:
            self.db.delete(record)

    def get_by_id(self, record_id: UUID) -> DunningLetterValidation:
        return self.db.get_by_id(record_id, DunningLetterValidation)

    def get_all(self) -> list:
        return self.db.get_all(DunningLetterValidation)

    def upsert(self, records) -> List[str]:
        return self.db.upsert(records, [], True, 1000)

    def get_by_ipr_and_date(self, ipr, validation_date):
        conditions = [
            lambda q: q.filter(DunningLetterValidation.IPR == ipr),
            lambda q: q.filter(func.date(DunningLetterValidation.ValidationDate) == validation_date),
        ]
        return self.db.get_with_condition(DunningLetterValidation, conditions)
