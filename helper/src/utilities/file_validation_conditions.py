from utilities.utility import Utility

class FileValidationCondition:
    def __init__(self, name, logMessage, description):
        self.name = name
        self.logMessage = logMessage
        self.description = description

class FileValidationConditions:
    FILENAME_AND_FILETYPE = "FilenameAndType"
    FILE_PROCESSED = "FileProcessed"
    FIRST_RECORD_ENDS_WITH_X = "FirstRecordEndsWithX"
    APPLICATION_DATE = "ApplicationDate"
    EXTRACT_DATE = "ExtractDate"
    CONDITION_JSON_FILE = "file_validation_conditions.json"

    def __init__(self, conditions: list[FileValidationCondition] | None = None):
        self.conditions = (
            Utility.load_from_json(
                FileValidationConditions, FileValidationConditions.CONDITION_JSON_FILE
            ).conditions
            if conditions is None or len(conditions) == 0
            else conditions
        )

    def get_condition(self, condition_name):
        for condition in self.conditions:
            if isinstance(condition, FileValidationCondition):
                con = condition
            else:
                con = FileValidationCondition(**condition)
            if con.name == condition_name:
                return con
        return None