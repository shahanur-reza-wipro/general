# assignment_letter_orchestration_service.py
import json
import logging
from typing import List

from repositories import DebtorRepository
from utilities.coniguration import Configuration
from utilities.sqs_helper import SQSHelper

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class AssignmentLetterOrchestrationService:
    """Queues all debtors in chunks to the assignment letter validation SQS queue."""

    def __init__(self):
        self.debtor_repository = DebtorRepository()
        self.configuration = Configuration().get_config()
        self.orchestration_queue_name = (
            self.configuration.assignmentLetterOrchestratorQueueName
        )
        self.integration_config_secret_name = (
            self.configuration.integrationConfigSecretName
        )

    def queue_to_validate_assignment_letter_generation(self, chunk_size=30):
        debtors = self.debtor_repository.get_all()

        if not debtors:
            logger.info("No debtors found for assignment letter generation.")
            return [], None

        submission_id = debtors[0].RunId
        queued_list = []

        for i in range(0, len(debtors), chunk_size):
            chunk = debtors[i: i + chunk_size]
            is_last_chunk = i + chunk_size >= len(debtors)

            payload = [
                {
                    "IPR": debtor.IPR,
                    "run_id": str(debtor.RunId),
                    "is_last_chunk": is_last_chunk,
                }
                for debtor in chunk
            ]

            self._send_to_sqs(payload)
            logger.info(f"{len(chunk)} debtors queued for assignment letter validation")
            queued_list.append(payload)

        return queued_list, submission_id

    def _send_to_sqs(self, iprs: List[dict]):
        sqs_helper = SQSHelper(
            self.orchestration_queue_name,
            self.integration_config_secret_name,
        )
        sqs_helper.send_message(json.dumps(iprs))
