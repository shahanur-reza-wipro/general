# assignment_letter_repository.py
from datetime import date
from typing import List
from uuid import UUID

from sqlalchemy import func, cast, String

from data_access_layer.models.assignment_letter import AssignmentLetter
from data_access_layer import Database
from .abstract_repository import AbstractRepository


class AssignmentLetterRepository(AbstractRepository):

    def __init__(self):
        self.db = Database()

    def add(self, record: AssignmentLetter) -> str:
        result = self.db.insert(record)
        if result:
            return str(result.ID)

    def update(self, record: AssignmentLetter) -> str:
        record = self.db.update(record)
        return str(record.ID)

    def delete(self, record_id: UUID):
        record = self.get_by_id(record_id)
        if record:
            self.db.delete(record)

    def get_by_id(self, record_id: UUID) -> AssignmentLetter:
        return self.db.get_by_id(record_id)

    def get_all(self) -> list:
        return self.db.get_all(AssignmentLetter)

    def upsert(self, records) -> List[str]:
        # exclude_id=True because ID is auto-generated
        return self.db.upsert(records, [], True, 500)

    def get_by_ipr_and_date(self, ipr, request_date):
        conditions = [
            lambda q: q.filter(AssignmentLetter.IPR == ipr),
            lambda q: q.filter(func.date(AssignmentLetter.RequestDateTime) == request_date),
        ]
        return self.db.get_with_condition(AssignmentLetter, conditions)

    def get_by_request_id(self, request_id):
        conditions = [
            lambda q: q.filter(AssignmentLetter.AssignmentLetterRequestId == request_id),
        ]
        return self.db.get_with_condition(AssignmentLetter, conditions)

    def get_assignment_letter_count_by_date(self, request_date, submission_id):
        with self.db.get_session() as session:
            count = (
                session.query(func.count(AssignmentLetter.ID))
                .filter(
                    func.date(AssignmentLetter.RequestDateTime) == request_date,
                    cast(AssignmentLetter.RunId, String) == str(submission_id),
                )
                .scalar()
            )
        return count or 0

    def get_assignment_letter_count_by_submission_id(self, submission_id):
        with self.db.get_session() as session:
            count = (
                session.query(func.count(AssignmentLetter.ID))
                .filter(cast(AssignmentLetter.RunId, String) == str(submission_id))
                .scalar()
            )
        return count or 0

    def get_distinct_assignment_request_id_by_date(self, request_date, submission_id):
        with self.db.get_session() as session:
            ids = (
                session.query(AssignmentLetter.AssignmentLetterRequestId)
                .filter(
                    func.date(AssignmentLetter.RequestDateTime) == request_date,
                    cast(AssignmentLetter.RunId, String) == str(submission_id),
                )
                .distinct()
                .all()
            )
        return ids or None

    def get_distinct_assignment_request_id_by_submission_id(self, submission_id):
        with self.db.get_session() as session:
            ids = (
                session.query(AssignmentLetter.AssignmentLetterRequestId)
                .filter(cast(AssignmentLetter.RunId, String) == str(submission_id))
                .distinct()
                .all()
            )
        return ids or None

    def get_assignment_by_opentext_ipr_and_date(self, ipr, request_date, submission_id):
        conditions = [
            lambda q: q.filter(AssignmentLetter.OpenTextIPR == ipr),
            lambda q: q.filter(func.date(AssignmentLetter.RequestDateTime) == request_date),
            lambda q: q.filter(cast(AssignmentLetter.RunId, String) == str(submission_id)),
        ]

        assignment_letters = self.db.get_with_condition(AssignmentLetter, conditions)

        if assignment_letters:
            return assignment_letters[0]

        return None

    def get_assignment_letters_by_request_date_with_pagination(self, request_date: date, submission_id, page_number=1, page_size=50):
        offset = (page_number - 1) * page_size

        conditions = [
            lambda q: q.filter(func.date(AssignmentLetter.RequestDateTime) == request_date),
            lambda q: q.filter(cast(AssignmentLetter.RunId, String) == str(submission_id)),
        ]

        letters = self.db.get_with_condition(
            AssignmentLetter,
            conditions,
            orderby=(AssignmentLetter.IPR, "asc"),
            offset=offset,
            limit=page_size,
        )

        return [
            {
                "IPR": letter.IPR,
                "RequestSubmissionStatus": letter.RequestSubmissionStatus,
                "FileName": letter.FileName,
            }
            for letter in letters
        ]
