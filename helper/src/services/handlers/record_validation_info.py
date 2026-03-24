class RecordValidationInfo:
    DEBTOR_RECORD_VALIDATOR = "DebtorRecordValidator"
    TRANSACTION_RECORD_VALIDATOR = "TransactionRecordValidator"

    def __init__(self, run_id, filename):
        self.run_id = run_id
        self.filename = filename
