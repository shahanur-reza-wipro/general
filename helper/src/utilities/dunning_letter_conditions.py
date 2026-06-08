from utilities.utility import Utility


class DunningLetterCondition:
    def __init__(self, name, logMessage, description):
        self.name = name
        self.logMessage = logMessage
        self.description = description


class DunningLetterConditions:
    DUNNING_ALREADY_REQUESTED_TODAY = "DunningAlreadyRequestedToday"
    HAS_VALID_TRANSACTIONS = "HasValidTransactions"
    DUNNING_FLAG = "DunningFlag"
    DUNNING_CYCLE_CODE = "DunningCycleCode"
    OVERDUE_ACCOUNT_BALANCE = "OverdueAccountBalance"
    CREDIT_CONTROLLER_DETAILS = "CreditControllerDetails"
    DEBTOR_EMAIL = "DebtorEmail"
    REQUEST_DUNNING_LETTER = "RequestDunningLetter"

    CONDITION_JSON_FILE = "dunning_letter_conditions.json"

    def __init__(self, conditions: list = []):
        self.conditions = (
            Utility.load_from_json(
                DunningLetterConditions,
                DunningLetterConditions.CONDITION_JSON_FILE,
            ).conditions
            if conditions is None or len(conditions) == 0
            else conditions
        )

    def get_condition(self, condition_name):
        for condition in self.conditions:
            con = DunningLetterCondition(**condition)
            if con.name == condition_name:
                return condition
        return None
