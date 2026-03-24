# statement_validation_repository.py
from typing import List, Union, overload
from data_access_layer import StatementValidation
from data_access_layer import Database
from .abstract_repository import AbstractRepository
from uuid import UUID
from datetime import date
from sqlalchemy import func


class StatementValidationRepository(AbstractRepository):

    def __init__(self):
        self.db = Database()

    def add(self, statement_validation: StatementValidation) -> str:
        self.db.insert(statement_validation)

    def update(self, statement_validation: StatementValidation) -> str:
        return str(statement_validation.ID)

    def delete(self, statement_validation_id: UUID):
        statement_validation = self.get_by_id(statement_validation_id)
        if statement_validation:
            self.db.delete(statement_validation)

    def get_by_id(self, statement_validation_id: UUID) -> StatementValidation:
        statement_validation = self.db.get_by_id(
            statement_validation_id, StatementValidation
        )
        return statement_validation

    def get_all(self) -> list:
        statement_validation = self.db.get_all(StatementValidation)
        return statement_validation

    def upsert(
        self,
        data: List[StatementValidation],
        excluded_columns: list = [],
        exclude_id=True,
        chunk_size=100,
    ):
        result = self.db.upsert(data, excluded_columns, exclude_id, chunk_size)
        return result

    def get_statement_validations_by_date(self, validation_date: date):

        conditions = [
            lambda q: q.filter(
                func.date(StatementValidation.StatementRequestDate) == validation_date
            )
        ]

        statement_validation_records = self.db.get_with_condition(
            StatementValidation, conditions
        )

        return statement_validation_records

    def get_statement_validations_logs_by_date_with_pagination(
        self,
        validation_date: date,
        submission_id,
        page_number=1,
        page_size=500,
    ):

        # implementing pagination
        offset = (page_number - 1) * page_size

        conditions = [
            lambda q: q.filter(
                func.date(StatementValidation.StatementRequestDate) == validation_date
            ),
            lambda q: q.filter(
                func.text(StatementValidation.RunId) == str(submission_id)
            ),
            lambda q: q.filter(
                StatementValidation.ConditionName != "RequestStatementGeneration"
            ),
        ]

        statement_validation_records = self.db.get_with_condition(
            StatementValidation,
            conditions,
            orderby=(StatementValidation.IPR, "asc"),
            offset=offset,
            limit=page_size,
        )

        statement_validation_records = [
            {
                "IPR": svr.IPR,
                "Log": svr.Log,
                "FileName": svr.FileName,
            }
            for svr in statement_validation_records
        ]

        return statement_validation_records