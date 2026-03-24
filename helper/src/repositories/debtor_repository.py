# debtor_repository.py
from datetime import datetime
from typing import List, Union
from data_access_layer.models import Debtor
from .abstract_repository import AbstractRepository
from data_access_layer import Database
from sqlalchemy.orm import sessionmaker, scoped_session


class DebtorRepository(AbstractRepository):

    def __init__(self):
        self.db = Database()

    def add(self, debtor: Debtor) -> str:
        self.db.insert(debtor)

    def update(self, entity: Debtor) -> str:
        return str(entity.IPR)

    def delete(self, ipr: str) -> None:
        debtor = self.get_by_id(ipr)
        self.db.delete(debtor)

    def delete_all(self) -> None:
        self.db.delete_all(Debtor)

    def get_by_id(self, ipr: str) -> Debtor:
        debtor = self.db.get_by_id(ipr, Debtor)
        return debtor

    def get_all(self) -> Union[List[Debtor], scoped_session]:
        debtors = self.db.get_all(Debtor)
        return debtors

    def upsert(self, debtors) -> List[str]:
        result = self.db.upsert(debtors, [], True, 1000)
        return result

    def get_debtors_by_stmt_run_day(self) -> Union[List[Debtor], scoped_session]:
        day = datetime.today().day
        day_str = str(day).zfill(2)
        conditions = [lambda q: q.filter(Debtor.StmtRunDay == day_str)]
        order_by = (Debtor.DebtorNumber, "asc")
        debtors = self.db.get_with_condition(Debtor, conditions, order_by)
        return debtors

    def get_debtors_by_iprs(self, iprs: list):
        return self.db.get_records_with_children(
            Debtor,
            Debtor.IPR.in_(iprs),
            [Debtor.Transactions, Debtor.RunControl]
        )

    def get_db_record_count(self, iprs: list):
        self.db.get_records(Debtor, Debtor.IPR.in_(iprs))

    def get_debtor_and_creditcontroller_email(self, iprs: list):
        debtors = self.db.get_records_with_children(Debtor, Debtor.IPR.in_(iprs))
        filtered_debtors = [
            {
                "IPR": debtor.IPR,
                "CreditController": debtor.CreditController,
                "DebtorStmtEmail": debtor.DebtorStmtEmail
            }
            for debtor in debtors
        ]
        return filtered_debtors