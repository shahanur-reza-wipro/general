from utilities import FixedLengthFileReader
from utilities import SchemaManager, Configuration
import os
import re


class FileService:

    def __init__(self):
        config = Configuration()
        self.configuration = config.get_config()
        self.file_reader = FixedLengthFileReader()
        self.schema_manager = SchemaManager()

    def get_records(self, file_object, model_name):
        schema = self.schema_manager.get_schema_by_model_name(model_name)
        records = self.file_reader.get_records(file_object, schema)
        #records = self.file_reader.get_records_with_regex(file_object, schema)
        return records

    def get_record(self, file_object, model_name, line_number):
        schema = self.schema_manager.get_schema_by_model_name(model_name)
        record = self.file_reader.get_record(file_object, schema, line_number)
        return record

    def validate_filetype(self, filename: str):
        # Validate file extension is same as filetype provided
        filetype = self.configuration.dataFileType
        return filename.endswith(filetype)

    def validate_filename(self, file: str):
        # Validate filename should match filename pattern
        filename_pattern = self.configuration.dataFileNamePattern
        filename = os.path.split(file)[1]
        return bool(re.match(filename_pattern, filename))