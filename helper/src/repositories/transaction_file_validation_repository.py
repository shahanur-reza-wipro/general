# transaction_file_validation_repository.py
from typing import List
from data_access_layer import TransactionFileValidation
from data_access_layer import Database
from .abstract_repository import AbstractRepository
from uuid import UUID


class TransactionFileValidationRepository(AbstractRepository):

    def __init__(self):
        self.db = Database()

    def add(self, transaction_validation_log: TransactionFileValidation) -> str:
        self.db.insert(transaction_validation_log)

    def upsert(self, transaction_validation_log: TransactionFileValidation) -> str:
        tvlg = self.db.upsert(transaction_validation_log)
        return str(tvlg.ID)

    def update(self, transaction_validation_log: TransactionFileValidation) -> str:
        return str(transaction_validation_log.ID)

    def delete(self, transaction_validation_log_id: UUID):
        transaction_validation_log = self.get_by_id(transaction_validation_log_id)
        if transaction_validation_log:
            self.db.delete(transaction_validation_log)

    def get_by_id(self, transaction_validation_log_id: UUID) -> TransactionFileValidation:
        transaction_validation_log = self.db.get_by_id(
            transaction_validation_log_id,
            TransactionFileValidation
        )
        return transaction_validation_log

    def get_by_filename(self, filename):
        condition = [
            lambda q: q.filter(TransactionFileValidation.FileName == filename)
        ]

        transaction_validation_log = self.db.get_with_condition(
            TransactionFileValidation,
            condition,
            orderby=(TransactionFileValidation.ID, "desc")
        )

        return transaction_validation_log

    def get_all(self) -> list:
        transaction_validation_log = self.db.get_all(TransactionFileValidation)
        return transaction_validation_log