# assignment_letter_conditions.py
from utilities.utility import Utility


class AssignmentLetterCondition:
    def __init__(self, name, logMessage, description):
        self.name = name
        self.logMessage = logMessage
        self.description = description


class AssignmentLetterConditions:
    ASSIGNMENT_ALREADY_REQUESTED_TODAY = "AssignmentAlreadyRequestedToday"
    HAS_VALID_TRANSACTIONS = "HasValidTransactions"
    INPAYMENT_DETAILS = "InpaymentDetails"
    ASSIGNMENT_DUE = "AssignmentDue"
    CREDIT_CONTROLLER_DETAILS = "CreditControllerDetails"
    DEBTOR_EMAIL = "DebtorEmail"
    REQUEST_ASSIGNMENT_LETTER = "RequestAssignmentLetter"

    CONDITION_JSON_FILE = "assignment_letter_conditions.json"

    def __init__(self, conditions: list = []):
        self.conditions = (
            Utility.load_from_json(
                AssignmentLetterConditions,
                AssignmentLetterConditions.CONDITION_JSON_FILE,
            ).conditions
            if conditions is None or len(conditions) == 0
            else conditions
        )

    def get_condition(self, condition_name):
        for condition in self.conditions:
            con = AssignmentLetterCondition(**condition)
            if con.name == condition_name:
                return condition
        return None
