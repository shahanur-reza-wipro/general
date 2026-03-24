import datetime
import logging
from repositories import StatementRequestRepository, StatementRepository
from utilities import SNSHelper, Configuration

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class StatementSubmitNotificationService:

    def __init__(self):
        self.statement_request_repository = StatementRequestRepository()
        self.statement_repository = StatementRepository()
        configuration = Configuration().get_config()
        self.sns_helper = SNSHelper(
            configuration.notificationTopicName,
            configuration.snsArnSecretName
        )
        self.statement_count = 0

    async def check_if_all_submission_is_done(self):
        today = datetime.date.today()
        expected_statement_count = (
            self.statement_request_repository.get_total_expected_statement_count(today)
        )
        self.statement_count = self.statement_repository.get_statement_count_by_date(today)
        return expected_statement_count == self.statement_count

    async def notify(self):
        if await self.check_if_all_submission_is_done():
            message_body = f"{self.statement_count} statements have been submitted"
            subject = (
                f"Submission has been Successfully done to OpenText on "
                f"{datetime.datetime.now()}"
            )
            notification_result = self.sns_helper.publish_message(message_body, subject)
            logger.info(f"Notification result: {notification_result}")