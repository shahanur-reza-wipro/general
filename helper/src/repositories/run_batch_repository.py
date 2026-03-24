# run_batch_repository.py

from typing import List, Union
from data_access_layer import Database, RunBatch
from .abstract_repository import AbstractRepository
from uuid import UUID
from sqlalchemy.orm import scoped_session
from sqlalchemy import and_, or_


class RunBatchRepository(AbstractRepository):

    def __init__(self):
        self.db = Database()

    def upsert(self, run_batch: RunBatch) -> str:
        rc = self.db.upsert(run_batch)
        return str(rc.ID)

    def update(self, run_batch: RunBatch) -> str:
        run_batch = self.db.update(run_batch)
        return str(run_batch.ID)

    def delete(self, run_batch_id: UUID):
        run_batch = self.get_by_id(run_batch_id)
        if run_batch:
            self.db.delete(run_batch)

    def delete_all(self):
        self.db.delete_all(RunBatch)

    def get_by_id(self, run_batch_id: UUID) -> RunBatch:
        run_batch = self.db.get_by_id(run_batch_id, RunBatch)
        return run_batch

    def get_runbatch_by_filename(self, filename, column):
        column_name = getattr(RunBatch, column)
        conditions = [lambda q: q.filter(column_name == filename)]
        run_batchs = self.db.get_with_condition(RunBatch, conditions)

        if run_batchs:
            return run_batchs[0]

        return None

    def get_all(self) -> list:
        return self.db.get_all(RunBatch)

    def upsert(self, run_batch) -> RunBatch:
        result = self.db.upsert(
            run_batch
        )  # exclude_id = True for auto-generated primary_key
        return result