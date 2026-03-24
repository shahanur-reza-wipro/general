from datetime import date

class FileValidationInfo:
    def __init__(self, filename: str, application_date: date, extract_date: date):
        self.filename = filename
        self.application_date = application_date
        self.extract_date = extract_date