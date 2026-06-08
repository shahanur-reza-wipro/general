# assignment_letter_generation_handler.py
from datetime import datetime

from data_access_layer.models.debtor import Debtor
from data_access_layer.models.assignment_letter_validation import AssignmentLetterValidation
from utilities import Utility, AssignmentLetterConditions, AssignmentLetterCondition
from repositories import (
    AssignmentLetterRepository,
    AssignmentLetterValidationRepository,
    RunControlRepository,
)


class AssignmentLetterGenerationHandler:
    """Base handler in the assignment letter chain-of-responsibility."""

    HANDLER_MAP = {}

    def __init__(self, successor=None):
        self.successor = successor
        self.assignment_letter_validation_repository = AssignmentLetterValidationRepository()
        self.run_control_repository = RunControlRepository()
        self.assignment_letter_repository = AssignmentLetterRepository()
        self.debtor_file_name_cache = {}
        self._conditions = None
        self.validation_log = None

    @property
    def conditions(self):
        if self._conditions is None:
            self._conditions = AssignmentLetterConditions()
        return self._conditions

    def build_chain(self, generation_conditions):
        chain = None
        for condition in reversed(generation_conditions):
            handle_class = self.HANDLER_MAP.get(condition)
            if handle_class:
                chain = handle_class(chain)
        return chain

    def log_condition(self, debtor: Debtor, condition_key: str) -> AssignmentLetterValidation:
        con_data = self.conditions.get_condition(condition_key)
        if not con_data:
            return None
        condition = AssignmentLetterCondition(**con_data)
        log = AssignmentLetterValidation(
            IPR=str(debtor.IPR),
            ConditionName=condition.name,
            Log=condition.logMessage,
            Description=condition.description,
            RunId=debtor.RunId,
            FileName=debtor.RunControl.DebtorFileName,
            ValidationDate=datetime.now(),
        )
        self.assignment_letter_validation_repository.upsert(log)
        self.validation_log = log
        return log

    def handle(self, debtor: Debtor):
        if self.successor:
            return self.successor.handle(debtor)
        return True


# ---------------------------------------------------------------------------
# Condition handlers
# ---------------------------------------------------------------------------

class AssignmentAlreadyRequestedTodayHandler(AssignmentLetterGenerationHandler):
    """Stop + log if an assignment letter was already requested today for this IPR."""

    def handle(self, debtor: Debtor):
        today = datetime.now().strftime("%Y-%m-%d")
        already_requested = self.assignment_letter_repository.get_by_ipr_and_date(
            debtor.IPR, today
        )
        if already_requested:
            self.log_condition(
                debtor, AssignmentLetterConditions.ASSIGNMENT_ALREADY_REQUESTED_TODAY
            )
            return False
        return super().handle(debtor)


class HasValidTransactionsHandler(AssignmentLetterGenerationHandler):
    """Stop + log when debtor has no valid transactions for letter generation."""

    def handle(self, debtor: Debtor):
        transactions = debtor.Transactions or []

        if not transactions:
            self.log_condition(debtor, AssignmentLetterConditions.HAS_VALID_TRANSACTIONS)
            return False

        return super().handle(debtor)


class AssignmentLetterInpaymentDetailsHandler(AssignmentLetterGenerationHandler):
    """Stop + log if any in-payment field is blank."""

    def handle(self, debtor: Debtor):
        present = (
            not Utility.is_none_or_empty(debtor.InpaymentBankCode)
            and not Utility.is_none_or_empty(debtor.InpaymentBankAccount)
            and not Utility.is_none_or_empty(debtor.InpaymentIbanNumber)
        )
        if not present:
            self.log_condition(debtor, AssignmentLetterConditions.INPAYMENT_DETAILS)
            return False
        return super().handle(debtor)


class AssignmentDueHandler(AssignmentLetterGenerationHandler):
    """Stop silently if AssignmentDue is not True (no log entry)."""

    def handle(self, debtor: Debtor):
        if not debtor.AssignmentDue:
            # Do NOT log – per spec: "If not due → do not log note"
            return False
        return super().handle(debtor)


class AssignmentLetterCreditControllerHandler(AssignmentLetterGenerationHandler):
    """Stop + log if credit controller is missing."""

    def handle(self, debtor: Debtor):
        if Utility.is_none_or_empty(debtor.CreditController):
            self.log_condition(
                debtor, AssignmentLetterConditions.CREDIT_CONTROLLER_DETAILS
            )
            return False
        return super().handle(debtor)


class AssignmentLetterDebtorEmailHandler(AssignmentLetterGenerationHandler):
    """Log missing email but CONTINUE – letter is still generated, manual delivery."""

    def handle(self, debtor: Debtor):
        if Utility.is_none_or_empty(debtor.DebtorStmEmail):
            self.log_condition(debtor, AssignmentLetterConditions.DEBTOR_EMAIL)
            # fall through – do NOT return False
        return super().handle(debtor)


class RequestAssignmentLetterHandler(AssignmentLetterGenerationHandler):
    """All conditions met – log the request and signal success."""

    def handle(self, debtor: Debtor):
        self.log_condition(debtor, AssignmentLetterConditions.REQUEST_ASSIGNMENT_LETTER)
        return super().handle(debtor)


# ---------------------------------------------------------------------------
# Wire up the HANDLER_MAP
# ---------------------------------------------------------------------------

AssignmentLetterGenerationHandler.HANDLER_MAP = {
    "AssignmentAlreadyRequestedToday": AssignmentAlreadyRequestedTodayHandler,
    "HasValidTransactions": HasValidTransactionsHandler,
    "InpaymentDetails": AssignmentLetterInpaymentDetailsHandler,
    "AssignmentDue": AssignmentDueHandler,
    "CreditControllerDetails": AssignmentLetterCreditControllerHandler,
    "DebtorEmail": AssignmentLetterDebtorEmailHandler,
    "RequestAssignmentLetter": RequestAssignmentLetterHandler,
}
