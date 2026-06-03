from datetime import date
from typing import Optional

class FileValidationInfo:
    def __init__(
        self,
        filename: str,
        application_date: date,
        extract_date: date,
        model_name: Optional[str] = None,
        first_record_end_field: Optional[str] = None,
        first_record_raw_line: Optional[str] = None,
        first_record_raw_line_length: Optional[int] = None,
    ):
        self.filename = filename
        self.application_date = application_date
        self.extract_date = extract_date
        self.model_name = model_name
        self.first_record_end_field = first_record_end_field
        self.first_record_raw_line = first_record_raw_line
        self.first_record_raw_line_length = first_record_raw_line_length