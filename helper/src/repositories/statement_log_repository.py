# statement_log_repository.py
from typing import List
from data_access_layer import StatementLog
from data_access_layer import Database
from .abstract_repository import AbstractRepository
from uuid import UUID
from datetime import date
from sqlalchemy import func


class StatementLogRepository(AbstractRepository):

    def __init__(self):
        self.db = Database()

    def add(self, statement_log: StatementLog) -> str:
        stmlg = self.db.upsert(statement_log)
        return str(stmlg.ID)

    def update(self, statement_log: StatementLog) -> str:
        return str(statement_log.ID)

    def delete(self, statement_log_id: UUID):
        statement_log = self.get_by_id(statement_log_id)
        if statement_log:
            self.db.delete(statement_log)

    def get_by_id(self, statement_log_id: UUID) -> StatementLog:
        statement_log = self.db.get_by_id(statement_log_id, StatementLog)
        return statement_log

    def get_all(self) -> list:
        statement_log = self.db.get_all(StatementLog)
        return statement_log

    def upsert(self, statement_logs) -> List[str]:
        result = self.db.upsert(statement_logs, 100, True)  # exclude_id = True for auto-generated primary_key
        return result

    def get_all_by_date(self, query_date: date):
        conditions = [lambda q: q.filter(func.date(StatementLog.StatementRequestDate) == query_date)]
        statement_log = self.db.get_with_condition(StatementLog, conditions)
        return statement_log