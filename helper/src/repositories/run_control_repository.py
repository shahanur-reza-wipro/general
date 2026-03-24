# run_control_repository.py

from typing import List, Union
from data_access_layer import RunControl
from data_access_layer import Database
from .abstract_repository import AbstractRepository
from uuid import UUID
from sqlalchemy.orm import scoped_session
from sqlalchemy import and_, or_


class RunControlRepository(AbstractRepository):

    def __init__(self):
        self.db = Database()
        self.COLUMN_MAPPER = {
            "Debtor": ("DebtorFileName", "HasDebtorFileProcessed"),
            "Transaction": ("TransactionFileName", "HasTransactionFileProcessed"),
        }

    def upsert(self, run_control: RunControl) -> str:
        rc = self.db.upsert(run_control)
        return str(rc.ID)

    def update(self, run_control: RunControl) -> str:
        run_control = self.db.update(run_control)
        return str(run_control.ID)

    def delete(self, run_control_id: UUID):
        run_control = self.get_by_id(run_control_id)
        if run_control:
            self.db.delete(run_control)

    def get_by_id(self, run_control_id: UUID) -> RunControl:
        run_control = self.db.get_by_id(run_control_id, RunControl)
        return run_control

    def get_all(self) -> list:
        return self.db.get_all(RunControl)

    def upsert(self, run_control) -> RunControl:
        result = self.db.upsert(
            run_control
        )  # exclude_id = True for auto-generated primary_key
        return result

    def get_run_control_by_date(
        self, application_date, extract_date
    ) -> Union[List[RunControl], scoped_session]:

        conditions = [
            lambda q: q.filter(RunControl.ApplicationDate == application_date),
            lambda q: q.filter(RunControl.ExtractDate == extract_date),
        ]

        run_controls = self.db.get_with_condition(RunControl, conditions)
        return run_controls

    def get_run_control_by_received_date_and_file_name(
        self, received_date, file_name
    ) -> Union[List[RunControl], scoped_session]:

        conditions = [
            lambda q: q.filter(RunControl.ReceivedDate == received_date),
            lambda q: q.filter(
                or_(
                    RunControl.DebtorFileName == file_name,
                    RunControl.TransactionFileName == file_name,
                )
            ),
            lambda q: q.filter(
                or_(
                    RunControl.HasDebtorFileProcessed == False,
                    RunControl.HasDebtorFileProcessed.is_(None),
                    RunControl.HasTransactionFileProcessed == False,
                    RunControl.HasTransactionFileProcessed.is_(None),
                )
            ),
        ]

        run_controls = self.db.get_with_condition(RunControl, conditions)
        return run_controls

    def get_run_control_by_filename(self, filename, column):
        column_name = getattr(RunControl, column)
        conditions = [lambda q: q.filter(column_name == filename)]
        run_controls = self.db.get_with_condition(RunControl, conditions)
        return run_controls

    def get_run_control_by_received_date(
        self, received_date
    ) -> Union[List[RunControl], scoped_session]:

        conditions = [
            lambda q: q.filter(
                and_(
                    RunControl.ReceivedDate == received_date,
                    or_(
                        RunControl.DebtorFileName.is_(None),
                        RunControl.TransactionFileName.is_(None),
                        RunControl.HasDebtorFileProcessed == False,
                        RunControl.HasDebtorFileProcessed.is_(None),
                        RunControl.HasTransactionFileProcessed == False,
                        RunControl.HasTransactionFileProcessed.is_(None),
                    ),
                )
            )
        ]

        run_controls = self.db.get_with_condition(RunControl, conditions)
        return run_controls

    def get_run_control_by_filename_already_processed(
        self, filename, column_file_name, column_file_processed
    ) -> Union[List[RunControl], scoped_session]:

        conditions = [
            lambda q: q.filter(getattr(RunControl, column_file_name) == filename),
            lambda q: q.filter(getattr(RunControl, column_file_processed) == True),
        ]

        run_controls = self.db.get_with_condition(RunControl, conditions)

        if run_controls:
            return run_controls[0]

        return None