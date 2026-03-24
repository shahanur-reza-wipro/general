from utilities import Configuration
from .file_validation_handler import (
    FilenameAndTypeHandler,
    FileProcessedHandler,
    ApplicationDateHandler,
    ExtractDateHandler,
)

class FileValidator:
    HANDLED_MAP = {
        "FilenameAndType": FilenameAndTypeHandler,
        "FileProcessed": FileProcessedHandler,
        "ApplicationDate": ApplicationDateHandler,
        "ExtractDate": ExtractDateHandler,
    }

    def __init__(self, file_validation_conditions):
        self.handler_chain = self.build_chain(file_validation_conditions)
        self.configuration = Configuration().get_config()

    def build_chain(self, file_validation_conditions):
        chain = None
        for condition in reversed(file_validation_conditions):
            handle_class = self.HANDLED_MAP.get(condition)
            if handle_class:
                chain = handle_class(chain)
        return chain

    def validate(self, file_validation_info, validation_logger):
        has_met_all_conditions = self.handler_chain.handle(file_validation_info, validation_logger)
        return has_met_all_conditions