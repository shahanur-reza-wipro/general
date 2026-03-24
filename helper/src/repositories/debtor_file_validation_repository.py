from typing import List
from data_access_layer import DebtorFileValidation
from data_access_layer import Database
from .abstract_repository import AbstractRepository
from uuid import UUID


class DebtorFileValidationRepository(AbstractRepository):

    def __init__(self):
        self.db = Database()

    def add(self, debtor_validation_log: DebtorFileValidation) -> str:
        self.db.insert(debtor_validation_log)

    def upsert(self, debtor_validation_log: DebtorFileValidation) -> str:
        dflv = self.db.upsert(debtor_validation_log)
        validation_log_id = str(dflv.ID)
        return validation_log_id

    def update(self, debtor_validation_log: DebtorFileValidation) -> str:
        return str(debtor_validation_log.ID)

    def delete(self, debtor_validation_log_id: UUID):
        debtor_validation_log = self.get_by_id(debtor_validation_log_id)
        if debtor_validation_log:
            self.db.delete(debtor_validation_log)

    def get_by_id(self, debtor_validation_log_id: UUID) -> DebtorFileValidation:
        debtor_validation_log = self.db.get_by_id(
            debtor_validation_log_id,
            DebtorFileValidation
        )
        return debtor_validation_log

    def get_by_filename(self, filename):
        condition = [
            lambda q: q.filter(DebtorFileValidation.FileName == filename)
        ]
        debtor_validation_log = self.db.get_with_condition(
            DebtorFileValidation,
            condition,
            orderby=(DebtorFileValidation.ValidationDateTime, "desc")
        )
        return debtor_validation_log

    def get_all(self) -> List:
        debtor_validation_log = self.db.get_all(DebtorFileValidation)
        return debtor_validation_log