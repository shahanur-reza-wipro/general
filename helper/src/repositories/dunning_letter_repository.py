# dunning_letter_repository.py
from datetime import date
from typing import List
from uuid import UUID

from sqlalchemy import func, cast, String

from data_access_layer.models.dunning_letter import DunningLetter
from data_access_layer import Database
from .abstract_repository import AbstractRepository


class DunningLetterRepository(AbstractRepository):

    def __init__(self):
        self.db = Database()

    def add(self, record: DunningLetter) -> str:
        result = self.db.insert(record)
        if result:
            return str(result.ID)

    def update(self, record: DunningLetter) -> str:
        record = self.db.update(record)
        return str(record.ID)

    def delete(self, record_id: UUID):
        record = self.get_by_id(record_id)
        if record:
            self.db.delete(record)

    def get_by_id(self, record_id: UUID) -> DunningLetter:
        return self.db.get_by_id(record_id)

    def get_all(self) -> list:
        return self.db.get_all(DunningLetter)

    def upsert(self, records) -> List[str]:
        # exclude_id=True because ID is auto-generated
        return self.db.upsert(records, [], True, 500)

    def get_by_ipr_and_date(self, ipr, request_date):
        conditions = [
            lambda q: q.filter(DunningLetter.IPR == ipr),
            lambda q: q.filter(func.date(DunningLetter.RequestDateTime) == request_date),
        ]
        return self.db.get_with_condition(DunningLetter, conditions)

    def get_by_request_id(self, request_id):
        conditions = [
            lambda q: q.filter(DunningLetter.DunningLetterRequestId == request_id),
        ]
        return self.db.get_with_condition(DunningLetter, conditions)

    def get_dunning_letter_count_by_date(self, request_date, submission_id):
        with self.db.get_session() as session:
            count = (
                session.query(func.count(DunningLetter.ID))
                .filter(
                    func.date(DunningLetter.RequestDateTime) == request_date,
                    cast(DunningLetter.RunId, String) == str(submission_id),
                )
                .scalar()
            )
        return count or 0

    def get_dunning_letter_count_by_submission_id(self, submission_id):
        with self.db.get_session() as session:
            count = (
                session.query(func.count(DunningLetter.ID))
                .filter(cast(DunningLetter.RunId, String) == str(submission_id))
                .scalar()
            )
        return count or 0

    def get_distinct_dunning_request_id_by_date(self, request_date, submission_id):
        with self.db.get_session() as session:
            ids = (
                session.query(DunningLetter.DunningLetterRequestId)
                .filter(
                    func.date(DunningLetter.RequestDateTime) == request_date,
                    cast(DunningLetter.RunId, String) == str(submission_id),
                )
                .distinct()
                .all()
            )
        return ids or None

    def get_distinct_dunning_request_id_by_submission_id(self, submission_id):
        with self.db.get_session() as session:
            ids = (
                session.query(DunningLetter.DunningLetterRequestId)
                .filter(cast(DunningLetter.RunId, String) == str(submission_id))
                .distinct()
                .all()
            )
        return ids or None

    def get_dunning_by_opentext_ipr_and_date(self, ipr, request_date, submission_id):
        conditions = [
            lambda q: q.filter(DunningLetter.OpenTextIPR == ipr),
            lambda q: q.filter(func.date(DunningLetter.RequestDateTime) == request_date),
            lambda q: q.filter(cast(DunningLetter.RunId, String) == str(submission_id)),
        ]

        dunning_letters = self.db.get_with_condition(DunningLetter, conditions)

        if dunning_letters:
            return dunning_letters[0]

        return None
