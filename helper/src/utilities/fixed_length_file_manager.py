from utilities.configuration import Configuration
from .schema_manager import Schema


class FixedLengthFileReader:

    def get_record(self, lines, schema: Schema, line_number):
        is_local = Configuration().get_config().isLocal
        sequence_number = 1
        for line in lines:
            if line == "" or line == "\n":
                continue

            raw_line = line.rstrip("\r\n")
            record = {}
            start_index = 0
            for property, length in zip(schema.get_model_properties(),
                                        schema.get_field_lengths()):
                record[property] = raw_line[start_index:start_index + length].strip()
                start_index += length + 1

            record["SeqId"] = sequence_number
            record["_raw_line"] = raw_line
            record["_raw_line_length"] = len(raw_line)

            if line_number == sequence_number:
                if is_local:
                    lines.seek(0)
                return record
            else:
                sequence_number += 1
                continue

    def get_records(self, lines, schema: Schema):
        records = []
        sequence_number = 1
        for line in lines:
            if line == "" or line == "\n":
                continue

            raw_line = line.rstrip("\r\n")
            record = {}
            start_index = 0
            for property, length in zip(schema.get_model_properties(),
                                        schema.get_field_lengths()):
                record[property] = raw_line[start_index:start_index + length].strip()
                start_index += length + 1

            record["SeqId"] = sequence_number
            record["_raw_line"] = raw_line
            record["_raw_line_length"] = len(raw_line)
            sequence_number += 1
            records.append(record)

        return records

 