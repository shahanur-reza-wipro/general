# dunning_letter_request_repository.py
from typing import List, Union
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import scoped_session

from data_access_layer.models.dunning_letter_request import DunningLetterRequest
from data_access_layer import Database
from .abstract_repository import AbstractRepository


class DunningLetterRequestRepository(AbstractRepository):

    def __init__(self):
        self.db = Database()

    def add(self, record: DunningLetterRequest) -> str:
        return self.db.insert(record)

    def update(self, record: DunningLetterRequest) -> str:
        return str(record.DunningLetterRequestID)

    def delete(self, record_id: UUID):
        record = self.get_by_id(record_id)
        if record:
            self.db.delete(record)

    def get_by_id(self, record_id: UUID) -> DunningLetterRequest:
        return self.db.get_by_id(record_id, DunningLetterRequest)

    def get_all(self) -> Union[List[DunningLetterRequest], scoped_session]:
        return self.db.get_all(DunningLetterRequest)

    def upsert(self, records) -> List[str]:
        return self.db.upsert(records, [], True, 1000)

    def get_total_request_submission(self, submission_id):
        with self.db.get_session() as session:
            count = (
                session.query(func.count(DunningLetterRequest.DunningLetterRequestID))
                .filter(DunningLetterRequest.SubmissionId == submission_id)
                .scalar()
            )
        return count or 0

    def get_distinct_submission_ids_by_date(self, request_date):
        with self.db.get_session() as session:
            submission_ids = (
                session.query(DunningLetterRequest.SubmissionId)
                .filter(
                    func.date(DunningLetterRequest.RequestDate) == request_date,
                    DunningLetterRequest.SubmissionId.isnot(None),
                )
                .distinct()
                .all()
            )
        return [str(row[0]) for row in submission_ids if row and row[0]]
