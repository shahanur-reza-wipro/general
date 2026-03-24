from utilities.coniguration import Configuration
from .schema_manager import Schema

class FixedLengthFileReader:
    def _parse_line(self, line, schema: Schema):
        record = {}
        properties = schema.get_model_properties()
        starts = schema.get_field_starts()
        lengths = schema.get_field_lengths()

        for property_name, start, length in zip(properties, starts, lengths):
            start_index = start - 1
            end_index = start_index + length
            record[property_name] = line[start_index:end_index].strip()

        return record

    def get_record(self, lines, schema: Schema, line_number):
        sequence_number = 1
        for line in lines:
            if line == "" or line == "\n":
                continue
            record = self._parse_line(line, schema)
            record["SeqId"] = sequence_number

            if line_number == sequence_number:
                if hasattr(lines, "seek"):
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
            record = self._parse_line(line, schema)
            record["SeqId"] = sequence_number
            sequence_number += 1
            records.append(record)
        
        return records
            