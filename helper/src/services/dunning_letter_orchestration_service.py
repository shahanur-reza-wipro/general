import json
import logging

from repositories import DebtorRepository
from utilities.sqs_helper import SQSHelper
from utilities.coniguration import Configuration

log = logging.getLogger(__name__)


class DunningLetterOrchestrationService:
    """Queues all debtors in chunks to the dunning letter validation SQS queue."""

    def __init__(self):
        self.configuration = Configuration().get_config()
        self.debtor_repository = DebtorRepository()
        self.dunning_orchestrator_queue_name = self.configuration.dunningLetterOrchestratorQueueName
        self.sqs_helper = SQSHelper(self.dunning_orchestrator_queue_name, self.configuration.integrationConfigSecretName)

    def queue_to_validate_dunning_letter_generation(self, chunk_size=30):
        debtors = self.debtor_repository.get_all()

        if not debtors:
            log.info("No debtors found for dunning letter generation.")
            return [], None

        submission_id = debtors[0].RunId
        queued_list = []

        for i in range(0, len(debtors), chunk_size):
            chunk = debtors[i:i + chunk_size]
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
            log.info(f"{len(chunk)} debtors queued for dunning letter validation")
            queued_list.append(payload)

        return queued_list, submission_id

    def _send_to_sqs(self, iprs):
        self.sqs_helper.send_message(json.dumps(iprs))
