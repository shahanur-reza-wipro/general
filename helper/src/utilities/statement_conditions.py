# statement_conditions.py
from utilities.utility import Utility


class StatementCondition:
    def __init__(self, name, logMessage, description):
        self.name = name
        self.logMessage = logMessage
        self.description = description


class StatementConditions:
    STATEMENT_REQUEST_TODAY = "StatementRequestedToday"
    IN_PAYMENT_DETAILS = "InpaymentDetails"
    STM_FLAG = "STMFlag"
    STM_RUN_DAY = "StatementRunDay"
    ACCOUNT_BAL_MIN = "AccountBalanceMin"
    ACCOUNT_BAL_MATCH = "AccountBalanceMatch"
    CREDIT_CONTROLLER_DETAILS = "CreditControllerDetails"
    DEBTOR_EMAIL = "DebtorEmail"
    REQUEST_STM_GENERATION = "RequestStatementGeneration"
    CONDITION_JSON_FILE = "statement_conditions.json"

    def __init__(self, conditions: list[StatementCondition] = []):
        self.conditions = (
            Utility.load_from_json(
                StatementConditions,
                StatementConditions.CONDITION_JSON_FILE,
            ).conditions
            if conditions is None or len(conditions) == 0
            else conditions
        )

    def get_condition(self, condition_name):
        for condition in self.conditions:
            con = StatementCondition(**condition)
            if con.name == condition_name:
                return condition
        return None