import json
import logging
from typing import List

from repositories import DebtorRepository
from services.files_processing_status_report_scheduler_service import FilesProcessingStatusReportSchedulerService
from utilities.coniguration import Configuration
from utilities.sqs_helper import SQSHelper

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class StatementOrchestrationService:

    def __init__(self):
        self.debtor_repository = DebtorRepository()
        self.configuration = Configuration().get_config()
        self.orchestration_queue_name = self.configuration.orchestratorQueueName
        self.integrationConfigSecretName = self.configuration.integrationConfigSecretName
        self.statement_generation_status_checker_service = FilesProcessingStatusReportSchedulerService()

    def queue_to_validate_statement_generation(self, chunk_size=30):
        debtors = self.debtor_repository.get_all()

        if debtors:
            queued_list_of_debtors = []
            submission_id = debtors[0].RunId

            # Chunk the list of debtors and send to SQS
            for i in range(0, len(debtors), chunk_size):
                chunked_debtors = debtors[i:i + chunk_size]
                is_last_chunk = i + chunk_size >= len(debtors)

                queued_iprs = self.send_to_sqs([
                    {
                        "IPR": debtor.IPR,
                        "run_id": str(debtor.RunId),
                        "is_last_chunk": is_last_chunk
                    }
                    for debtor in chunked_debtors
                ])

                logger.info(
                    f"{len(chunked_debtors)} has been queued for statement validation"
                )

                queued_list_of_debtors.append(queued_iprs)

            payload = {
                "submission_id": str(submission_id)
            }

            if self.configuration.isLocal:
                logger.info("Local mode enabled. Skipping EventBridge scheduling for statement reports.")
            else:
                # schedule file processing report generation lambda for every 5 mins
                self.statement_generation_status_checker_service.schedule_statement_status_report_generation(
                    self.configuration.fileProcessedReportGeneratorLambdaDetailsSecretName,
                    self.configuration.processingReportGenerationAttemptInterval,
                    True,
                    payload
                )

                # schedule file summary report generation lambda for every 60 mins
                self.statement_generation_status_checker_service.schedule_statement_status_report_generation(
                    self.configuration.fileSummaryReportGeneratorLambdaDetailsSecretName,
                    self.configuration.summaryReportGenerationAttemptInterval,
                    False,
                    payload
                )

            return queued_list_of_debtors, submission_id

        logger.info("No debtors were found for statement generation.")

    def send_to_sqs(self, iprs: List[dict]):
        sqs_helper = SQSHelper(
            self.orchestration_queue_name,
            self.integrationConfigSecretName
        )

        message_body = json.dumps(iprs)
        queue_response = sqs_helper.send_message(message_body)

        return iprs