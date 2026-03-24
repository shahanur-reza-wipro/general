from utilities.utility import Utility

class RecordCondition:
    def __init__(self, name, logMessage, description):
        self.name = name
        self.logMessage = logMessage
        self.description = description

class RecordConditions():
    CHECK_INVALID_IPR = "CheckInvalidIPR"
    END_WITH_X = "EndsWithX"
    FIELD_FORMAT = "FieldFormat"
    CONDITION_JSON_FILE = "record_conditions.json"

    def __init__(self, conditions: list[RecordCondition] = []):
        self.conditions = (
            Utility.load_from_json(
                RecordConditions, RecordConditions.CONDITION_JSON_FILE
            ).conditions
            if not conditions or len(conditions) == 0
            else conditions
        )

    def get_condition(self, condition_name):
        for condition in self.conditions:
            con = RecordCondition(**condition)
            if con.name == condition_name:
                return con
        return None