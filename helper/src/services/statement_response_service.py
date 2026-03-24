import datetime
import logging
from repositories import StatementRepository
from data_access_layer import Statement

log = logging.getLogger()


class StatementResponseService:

    def __init__(self):
        self.statement_repository = StatementRepository()

    def update_statements_for_open_text_response(self, ipr_status_list, submission_id):
        # update opentext_response in statement table
        today = datetime.now().strftime("%Y-%m-%d")
        statements = []

        for ipr_status in ipr_status_list:
            ipr = ipr_status["IPR"]
            processing_status = ipr_status["Statement Processing Status"]
            reason_for_failure = ipr_status["Reason For Failure"]

            statement = self.statement_repository.get_statement_by_opentext_ipr_and_date(
                ipr, today, submission_id
            )

            if statement is not None:
                if processing_status is not None:
                    statement.StatementProcessingStatus = processing_status

                if reason_for_failure is not None:
                    statement.ReasonForFailure = reason_for_failure

                statements.append(statement)
            else:
                log.info(f"statement was not be found for {submission_id}")

        unique_statements = list({s.id: s for s in statements}.values())

        result = self.statement_repository.upsert(unique_statements)

        log_message = f"{len(result)} statements has been updated successfully"
        log.info(log_message)