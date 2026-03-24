from datetime import datetime
from data_access_layer.models import Debtor, StatementValidation
from utilities import Utility, StatementConditions, StatementCondition
from repositories import StatementRepository, RunControlRepository, StatementValidationRepository

class StatementGenerationHandler:
    HANDLER_MAP = {}

    def __init__(self, successor=None):
        self.successor = successor
        self.statement_validation_repository = StatementValidationRepository()
        self.run_control_repository = RunControlRepository()
        self.statement_repository = StatementRepository()
        self.debtor_file_name_cache = {}
        self._statement_conditions = None
        self.statement_validation = None
    
    @property
    def statement_conditions(self):
        if self._statement_conditions is None:
            self._statement_conditions = StatementConditions()
        return self._statement_conditions
    
    def build_chain(self, statement_generation_conditions):
        chain = None
        for condition in reversed(statement_generation_conditions):
            handle_class = self.HANDLER_MAP.get(condition)
            if handle_class:
                chain = handle_class(chain)
        return chain
    
    def get_debtor_file_name(self, runcontrol_id):
        if runcontrol_id not in self.debtor_file_name_cache:
            run_control = self.run_control_repository.get_run_control(runcontrol_id)
            self.debtor_file_name_cache[runcontrol_id] = run_control.debtor_file_name
        return self.debtor_file_name_cache[runcontrol_id]
    
    def log_state_operation(self, debtor:Debtor, con:StatementCondition) -> str:
        condition = StatementCondition(*con)
        log = StatementValidation(
            IPR=str(debtor.IPR),
            ConditionName=condition.name,
            Log=condition.logMessage,
            Description=condition.description,
            RunId=debtor.RunId,
            FileName=debtor.RunControl.DebtorFileName,
            StatementRequestDate=datetime.now()
        )
        log_id = self.statement_validation_repository.upsert(log)
        self.statement_validation = log
    
    def handle(self, debtor: Debtor):
        if self.successor:
            return self.successor.handle(debtor)
        return True


class StatementRequestedTodayHandler(StatementGenerationHandler):
    def handle(self, debtor: Debtor):
        today_date = datetime.now().strftime("%Y-%m-%d")
        statement_requested_today = self.statement_repository.get_stm_by_ipr_and_date(
            debtor.IPR, today_date
        )
        if statement_requested_today:
            statement_condition = self.statement_conditions.get_condition(
                StatementConditions.STATEMENT_REQUEST_TODAY
            )
            self.statement_validation = self.log_state_operation(debtor, statement_condition)
            return False
        return super().handle(debtor)


class InpaymentDetailsHandler(StatementGenerationHandler):
    def handle(self, debtor: Debtor):
        inpayment_details_available = (
            not Utility.is_none_or_empty(debtor.InpaymentBankAccount)
            and not Utility.is_none_or_empty(debtor.InpaymentBankCode)
            and not Utility.is_none_or_empty(debtor.InpaymentIbanNumber)
        )
        if not inpayment_details_available:
            statement_condition = self.statement_conditions.get_condition(
                StatementConditions.IN_PAYMENT_DETAILS
            )
            self.log_state_operation(debtor, statement_condition)
            return False
        return super().handle(debtor)


class STMFlagHandler(StatementGenerationHandler):
    def handle(self, debtor: Debtor):
        if not debtor.StmFlag:
            statement_condition = self.statement_conditions.get_condition(
                StatementConditions.STM_FLAG
            )
            self.log_state_operation(debtor, statement_condition)
            return False
        return super().handle(debtor)


class StatementRunDayHandler(StatementGenerationHandler):
    def handle(self, debtor: Debtor):
        today = datetime.today()
        day = today.day
        day_str = str(day).zfill(2)
        if day_str != debtor.StmRunDay:
            statement_condition = self.statement_conditions.get_condition(
                StatementConditions.STM_RUN_DAY
            )
            self.log_state_operation(debtor, statement_condition)
            return False
        return super().handle(debtor)


class AccountBalanceMinHandler(StatementGenerationHandler):
    def handle(self, debtor: Debtor):
        if debtor.CustomerAccountBalance < 25:
            statement_condition = self.statement_conditions.get_condition(
                StatementConditions.ACCOUNT_BAL_MIN
            )
            self.log_state_operation(debtor, statement_condition)
            return False
        return super().handle(debtor)


class AccountBalanceMatchHandler(StatementGenerationHandler):
    def handle(self, debtor: Debtor):
        total_open_item_balance = sum(
            transaction.ItemBalance for transaction in debtor.Transactions
        )
        if debtor.CustomerAccountBalance != total_open_item_balance:
            statement_condition = self.statement_conditions.get_condition(
                StatementConditions.ACCOUNT_BAL_MATCH
            )
            self.log_state_operation(debtor, statement_condition)
            return False
        return super().handle(debtor)


class CreditControllerDetailsHandler(StatementGenerationHandler):
    def handle(self, debtor: Debtor):
        if Utility.is_none_or_empty(debtor.CreditController):
            # logged for the IPR "Missing Credit Controller" along with the IPR number
            # continue even if the condition fails
            statement_condition = self.statement_conditions.get_condition(
                StatementConditions.CREDIT_CONTROLLER_DETAILS
            )
            self.log_state_operation(debtor, statement_condition)
            pass
        return super().handle(debtor)


class DebtorEmailHandler(StatementGenerationHandler):
    def handle(self, debtor: Debtor):
        if Utility.is_none_or_empty(debtor.DebtorStmEmail):
            # logged for the IPR "Missing Debtor Email" along with the IPR number
            # continue even if the condition fails
            statement_condition = self.statement_conditions.get_condition(
                StatementConditions.DEBTOR_EMAIL
            )
            self.log_state_operation(debtor, statement_condition)
            pass
        return super().handle(debtor)


class RequestStatementGenerationHandler(StatementGenerationHandler):
    def handle(self, debtor: Debtor):
        # log the statement generation has been requested with IPR and date
        statement_condition = self.statement_conditions.get_condition(
            StatementConditions.REQUEST_STM_GENERATION
        )
        self.log_state_operation(debtor, statement_condition)
        return super().handle(debtor)


# Initialize the handler map
StatementGenerationHandler.HANDLER_MAP = {
    "StatementRequestedToday": StatementRequestedTodayHandler,
    "InpaymentDetails": InpaymentDetailsHandler,
    "STMFlag": STMFlagHandler,
    "StatementRunDay": StatementRunDayHandler,
    "AccountBalanceMin": AccountBalanceMinHandler,
    "AccountBalanceMatch": AccountBalanceMatchHandler,
    "CreditControllerDetails": CreditControllerDetailsHandler,
    "DebtorEmail": DebtorEmailHandler,
    "RequestStatementGeneration": RequestStatementGenerationHandler,
}

