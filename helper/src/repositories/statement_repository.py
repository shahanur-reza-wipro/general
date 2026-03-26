# statement_repository.py

from typing import List
from sqlalchemy import func, cast, String
from data_access_layer.models import Statement
from data_access_layer import Database
from .abstract_repository import AbstractRepository
from uuid import UUID
from datetime import date


class StatementRepository(AbstractRepository):

    def __init__(self):
        self.db = Database()

    def add(self, statement: Statement) -> str:
        stm = self.db.insert(statement)
        if stm:
            return str(stm.ID)

    def update(self, statement: Statement) -> str:
        statement = self.db.update(statement)
        return str(statement.ID)

    def delete(self, statement_id: UUID):
        statement = self.get_by_id(statement_id)
        if statement:
            self.db.delete(statement)

    def get_by_id(self, statement_id: UUID) -> Statement:
        statement = self.db.get_by_id(statement_id)
        return statement

    def get_all(self) -> list:
        statements = self.db.get_all(Statement)
        return statements

    def upsert(self, statements) -> List[str]:
        result = self.db.upsert(statements, [], True, 500)  # exclude_id = True for auto-generated primary_key
        return result

    def get_stm_by_ipr_and_date(self, ipr, date):
        conditions = [
            lambda q: q.filter(Statement.IPR == ipr),
            lambda q: q.filter(func.date(Statement.StatementRequestDateTime) == date),
        ]
        statement = self.db.get_with_condition(Statement, conditions)
        return statement

    def get_statement_by_request_id_and_pdffile_name(self, request_id, open_text_ipr):
        conditions = [
            lambda q: q.filter(Statement.StatementRequestId == request_id),
            lambda q: q.filter(Statement.OpenTextIPR == open_text_ipr),
        ]
        statements = self.db.get_with_condition(Statement, conditions)

        if statements:
            return statements[0]

        return None

    def get_statements_by_request_id_and_opentextiprs(self, request_id, opentext_iprs: list):
        conditions = [
            lambda q: q.filter(Statement.StatementRequestId == request_id),
            lambda q: q.filter(Statement.OpenTextIPR.in_(opentext_iprs)),
        ]

        statements = self.db.get_with_condition(Statement, conditions)

        if statements:
            return statements

        return None

    def get_statement_count_by_date(self, statement_request_date, submission_id):
        with self.db.get_session() as session:
            count = (
                session.query(func.count(Statement.ID))
                .filter(
                    func.date(Statement.StatementRequestDateTime) == statement_request_date,
                    cast(Statement.RunId, String) == str(submission_id),
                )
                .scalar()
            )

        return count or 0

    def get_statement_count_by_submission_id(self, submission_id):
        with self.db.get_session() as session:
            count = (
                session.query(func.count(Statement.ID))
                .filter(cast(Statement.RunId, String) == str(submission_id))
                .scalar()
            )

        return count or 0

    def get_statements_by_request_date(self, statement_request_date: date):
        conditions = [
            lambda q: q.filter(func.date(Statement.StatementRequestDateTime) == statement_request_date)
        ]

        statements = self.db.get_with_condition(Statement, conditions)
        return statements

    def get_distinct_statement_request_id_by_date(self, statement_request_date: date, submission_id):
        with self.db.get_session() as session:
            distinct_statement_request_ids = (
                session.query(Statement.StatementRequestId)
                .filter(
                    func.date(Statement.StatementRequestDateTime) == statement_request_date,
                    cast(Statement.RunId, String) == str(submission_id),
                )
                .distinct()
                .all()
            )

        if distinct_statement_request_ids:
            return distinct_statement_request_ids

        return None

    def get_distinct_statement_request_id_by_submission_id(self, submission_id):
        with self.db.get_session() as session:
            distinct_statement_request_ids = (
                session.query(Statement.StatementRequestId)
                .filter(cast(Statement.RunId, String) == str(submission_id))
                .distinct()
                .all()
            )

        if distinct_statement_request_ids:
            return distinct_statement_request_ids

        return None

    def get_stm_by_opentext_ipr_and_date(self, ipr, date, submission_id):
        conditions = [
            lambda q: q.filter(Statement.OpenTextIPR == ipr),
            lambda q: q.filter(func.date(Statement.StatementRequestDateTime) == date),
            lambda q: q.filter(cast(Statement.RunId, String) == str(submission_id)),
        ]

        statements = self.db.get_with_condition(Statement, conditions)

        if statements:
            return statements[0]

        return None

    def get_statements_by_request_date_with_pagination(self, statement_request_date: date, submission_id, page_number=1, page_size=50):
        offset = (page_number - 1) * page_size

        conditions = [
            lambda q: q.filter(func.date(Statement.StatementRequestDateTime) == statement_request_date),
            lambda q: q.filter(cast(Statement.RunId, String) == str(submission_id)),
        ]

        statements = self.db.get_with_condition(
            Statement,
            conditions,
            orderby=(Statement.IPR, "asc"),
            offset=offset,
            limit=page_size,
        )

        statements = [
            {
                "IPR": statement.IPR,
                "RequestSubmissionStatus": statement.RequestSubmissionStatus,
                "FileName": statement.FileName,
            }
            for statement in statements
        ]

        return statements