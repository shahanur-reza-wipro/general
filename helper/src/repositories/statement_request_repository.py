# statement_request_repository.py
from typing import List, Union

from sqlalchemy import func

from data_access_layer.models import StatementRequest
from .abstract_repository import AbstractRepository
from data_access_layer import Database
from sqlalchemy.orm import scoped_session


class StatementRequestRepository(AbstractRepository):

    def __init__(self):
        self.db = Database()

    def add(self, statementRequest: StatementRequest) -> str:
        return self.db.insert(statementRequest)

    def update(self, entity: StatementRequest) -> str:
        return str(entity.StatementRequestID)

    def delete(self, statementRequestID: str) -> None:
        statementRequest = self.get_by_id(statementRequestID)
        self.db.delete(statementRequest)

    def get_by_id(self, statementRequestID: str) -> StatementRequest:
        statementRequest = self.db.get_by_id(statementRequestID, StatementRequest)
        return statementRequest

    def get_all(self) -> Union[list[StatementRequest], scoped_session]:
        statementRequests = self.db.get_all(StatementRequest)
        return statementRequests

    def upsert(self, statementRequests) -> List[str]:
        result = self.db.upsert(statementRequests, [], True, 1000)
        return result

    def get_total_expected_statement_count(self, submission_date):
        with self.db.get_session() as session:
            total_count = (
                session.query(func.sum(StatementRequest.ExpectedStatementCount))
                .filter(func.date(StatementRequest.StatementRequestDate) == submission_date)
                .scalar()
            )
        return total_count or 0

    def get_total_request_submission(self, submission_id):
        with self.db.get_session() as session:
            count = (
                session.query(func.count(StatementRequest.StatementRequestID))
                .filter(StatementRequest.SubmissionId == submission_id)
                .scalar()
            )
        return count or 0

    def get_distinct_submission_ids_by_date(self, request_date):
        with self.db.get_session() as session:
            submission_ids = (
                session.query(StatementRequest.SubmissionId)
                .filter(
                    func.date(StatementRequest.StatementRequestDate) == request_date,
                    StatementRequest.SubmissionId.isnot(None),
                )
                .distinct()
                .all()
            )
        return submission_ids or []