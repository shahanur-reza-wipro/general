from datetime import datetime
import uuid

from data_access_layer.models.debtor import Debtor
from data_access_layer.models.dunning_letter_validation import DunningLetterValidation
from utilities import Utility, DunningLetterConditions, DunningLetterCondition
from repositories import DunningLetterRepository, DunningLetterValidationRepository


class DunningLetterGenerationHandler:
    """Base handler in the dunning letter chain-of-responsibility."""

    HANDLER_MAP = {}
    VALID_DUNNING_CYCLE_CODES = {"5200", "5201", "5202"}

    def __init__(self, successor=None):
        self.successor = successor
        self.dunning_letter_repository = DunningLetterRepository()
        self.dunning_letter_validation_repository = DunningLetterValidationRepository()
        self._conditions = None

    @property
    def conditions(self):
        if self._conditions is None:
            self._conditions = DunningLetterConditions()
        return self._conditions

    def build_chain(self, generation_conditions):
        chain = None
        for condition in reversed(generation_conditions):
            handle_class = self.HANDLER_MAP.get(condition)
            if handle_class:
                chain = handle_class(chain)
        return chain

    def log_condition(self, debtor: Debtor, condition_key: str, override_message: str = None, passed: bool = False):
        con_data = self.conditions.get_condition(condition_key)
        if not con_data:
            return None

        condition = DunningLetterCondition(**con_data)
        log = DunningLetterValidation(
            ID=uuid.uuid4(),
            IPR=str(debtor.IPR),
            ConditionName=condition.name,
            Log=(override_message or condition.logMessage),
            Description=condition.description,
            RunId=debtor.RunId,
            FileName=debtor.RunControl.DebtorFileName,
            ValidationDate=datetime.now().date(),
        )
        self.dunning_letter_validation_repository.upsert(log)
        return log

    def handle(self, debtor: Debtor):
        if self.successor:
            return self.successor.handle(debtor)
        return True


class DunningAlreadyRequestedTodayHandler(DunningLetterGenerationHandler):
    def handle(self, debtor: Debtor):
        today = datetime.now().strftime("%Y-%m-%d")
        already_requested = self.dunning_letter_repository.get_by_ipr_and_date(debtor.IPR, today)
        if already_requested:
            self.log_condition(debtor, DunningLetterConditions.DUNNING_ALREADY_REQUESTED_TODAY)
            return False
        return super().handle(debtor)


class DunningFlagHandler(DunningLetterGenerationHandler):
    def handle(self, debtor: Debtor):
        dunning_flag = (
            getattr(debtor, "DunningReminderFlag", None)
            or getattr(debtor, "DunningReminder", None)
            or getattr(debtor, "DunningFlag", 0)
        )

        if int(dunning_flag or 0) == 0:
            # Per spec: stop silently when dunning flag is 0 (no log)
            return False

        if int(dunning_flag) not in [1, 2, 3]:
            self.log_condition(
                debtor,
                DunningLetterConditions.DUNNING_FLAG,
                override_message=f"Invalid Dunning Flag: {dunning_flag}",
            )
            return False

        return super().handle(debtor)


class DunningCycleCodeHandler(DunningLetterGenerationHandler):
    def handle(self, debtor: Debtor):
        cycle_code = str(getattr(debtor, "DunningCycleCode", "") or "").strip()
        if cycle_code not in self.VALID_DUNNING_CYCLE_CODES:
            self.log_condition(
                debtor,
                DunningLetterConditions.DUNNING_CYCLE_CODE,
                override_message="Unknown Dunning Cycle Code",
            )
            return False
        return super().handle(debtor)


class DunningAccountBalanceHandler(DunningLetterGenerationHandler):
    def handle(self, debtor: Debtor):
        account_balance = float(getattr(debtor, "CustomerAccountBalance", 0) or 0)
        if account_balance <= 0:
            self.log_condition(debtor, DunningLetterConditions.ACCOUNT_BALANCE)
            return False
        return super().handle(debtor)


class DunningCreditControllerHandler(DunningLetterGenerationHandler):
    def handle(self, debtor: Debtor):
        if Utility.is_none_or_empty(getattr(debtor, "CreditController", None)):
            self.log_condition(debtor, DunningLetterConditions.CREDIT_CONTROLLER_DETAILS)
            return False
        return super().handle(debtor)


class DunningDebtorEmailHandler(DunningLetterGenerationHandler):
    def handle(self, debtor: Debtor):
        debtor_email = getattr(debtor, "DebtorStmEmail", None)
        if Utility.is_none_or_empty(debtor_email):
            # Per spec: log but continue
            self.log_condition(debtor, DunningLetterConditions.DEBTOR_EMAIL)
        return super().handle(debtor)


class RequestDunningLetterHandler(DunningLetterGenerationHandler):
    def handle(self, debtor: Debtor):
        self.log_condition(
            debtor,
            DunningLetterConditions.REQUEST_DUNNING_LETTER,
            passed=True,
        )
        return super().handle(debtor)


DunningLetterGenerationHandler.HANDLER_MAP = {
    "DunningAlreadyRequestedToday": DunningAlreadyRequestedTodayHandler,
    "DunningFlag": DunningFlagHandler,
    "DunningCycleCode": DunningCycleCodeHandler,
    "AccountBalance": DunningAccountBalanceHandler,
    "CreditControllerDetails": DunningCreditControllerHandler,
    "DebtorEmail": DunningDebtorEmailHandler,
    "RequestDunningLetter": RequestDunningLetterHandler,
}
