# transaction_repository.py
from typing import List
from data_access_layer.models import Transaction
from .abstract_repository import AbstractRepository
from data_access_layer import Database


class TransactionRepository(AbstractRepository):

    def __init__(self):
        self.db = Database()

    def add(self, transaction: Transaction) -> str:
        self.db.insert(transaction)

    def update(self, transaction: Transaction) -> str:
        transaction = self.db.update(transaction)
        return str(transaction.TransactionId)

    def delete_all(self) -> None:
        self.db.delete_all(Transaction)

    def delete(self, transaction_id: str) -> None:
        transaction = self.get_by_id(transaction_id)
        if transaction:
            self.db.delete(transaction)

    def get_by_id(self, transaction_id: str) -> Transaction:
        return self.db.get_by_id(transaction_id, Transaction)

    def get_all(self) -> list:
        return self.db.get_all(Transaction)

    def upsert(self, transactions) -> List[str]:
        result = self.db.upsert(transactions, [], True, 1000)
        return result