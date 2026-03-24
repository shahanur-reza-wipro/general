# assignment_letter_request_repository.py
from typing import List, Union
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import scoped_session

from data_access_layer.models.assignment_letter_request import AssignmentLetterRequest
from data_access_layer import Database
from .abstract_repository import AbstractRepository


class AssignmentLetterRequestRepository(AbstractRepository):

    def __init__(self):
        self.db = Database()

    def add(self, record: AssignmentLetterRequest) -> str:
        return self.db.insert(record)

    def update(self, record: AssignmentLetterRequest) -> str:
        return str(record.AssignmentLetterRequestID)

    def delete(self, record_id: UUID) -> None:
        record = self.get_by_id(record_id)
        self.db.delete(record)

    def get_by_id(self, record_id) -> AssignmentLetterRequest:
        return self.db.get_by_id(record_id, AssignmentLetterRequest)

    def get_all(self) -> Union[List[AssignmentLetterRequest], scoped_session]:
        return self.db.get_all(AssignmentLetterRequest)

    def upsert(self, records) -> List[str]:
        return self.db.upsert(records, [], True, 1000)

    def get_total_request_submission(self, submission_id):
        with self.db.get_session() as session:
            count = (
                session.query(func.count(AssignmentLetterRequest.AssignmentLetterRequestID))
                .filter(AssignmentLetterRequest.SubmissionId == submission_id)
                .scalar()
            )
        return count or 0

    def get_distinct_submission_ids_by_date(self, request_date):
        with self.db.get_session() as session:
            submission_ids = (
                session.query(AssignmentLetterRequest.SubmissionId)
                .filter(
                    func.date(AssignmentLetterRequest.RequestDate) == request_date,
                    AssignmentLetterRequest.SubmissionId.isnot(None),
                )
                .distinct()
                .all()
            )
        return submission_ids or []
