import asyncio
from .record_validation_handler import (
    EndWithXHandler,
    FieldFormatHandler,
    CheckInvalidIPRHandler
)
from itertools import groupby

class RecordValidator:
    HANDLED_MAP = {
        "EndWithX": EndWithXHandler,
        "FieldFormat": FieldFormatHandler,
        "CheckInvalidIPR": CheckInvalidIPRHandler,
    }

    def __init__(self, record_validation_conditions):
        self.handler_chain = self.build_chain(record_validation_conditions)
        self.request_queue = asyncio.Queue()
        self.invalid_iprs = []

    def build_chain(self, record_validation_conditions):
        chain = None
        for condition in reversed(record_validation_conditions):
            handle_class = self.HANDLED_MAP.get(condition)
            if handle_class:
                chain = handle_class(chain)
        return chain

    async def validate_records(self, records, record_validation_info, validation_logger):
        # group records by IPR
        records_grouped_by_ipr = self.group_by_ipr(records)
        validated_records = []
        tasks = []

        for IPR, grouped_records in records_grouped_by_ipr.items():
            task = asyncio.create_task(self.validate(grouped_records, record_validation_info, validation_logger))
            tasks.append(task)

        # gather all tasks    
        results = await asyncio.gather(*tasks)
        # flatten list of records
        records = [req for sublist in results for req in sublist]
        print("[DEBUG] records before validated_records filter:")
        for idx, record in enumerate(records):
            print(
                f"[DEBUG] idx={idx}, type={type(record)}, has_ipr={hasattr(record, 'IPR')}, ipr={getattr(record, 'IPR', None)}"
            )
        # prepare list of valid records
        validated_records = [
            record
            for record in records
            if record and record.IPR not in self.invalid_iprs
        ]
        # has_met_all_conditions = self.handler_chain.handle(records[0], record_validation_info, validation_logger, self.invalid_iprs)
        return validated_records, self.invalid_iprs
    
    def group_by_ipr(self, records):
        sorted_records = sorted(records, key=lambda r: r.IPR)
        # group records by IPR
        grouped_records_by_ipr = {IPR: list(group) for IPR, group in groupby(sorted_records, key=lambda r: r.IPR)}
        return grouped_records_by_ipr

    async def validate(self, records, record_validation_info, validation_logger):
        tasks = [
            self.validate_record(record, record_validation_info, validation_logger)
            for record in records
            if record
        ]
        records = await asyncio.gather(*tasks)
        return records

    async def validate_record(self, record, record_validation_info, validation_logger):
        has_met_all_conditions = self.handler_chain.handle(record, record_validation_info, validation_logger, self.invalid_iprs)
        record = record if has_met_all_conditions else None
        return record
