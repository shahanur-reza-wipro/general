from typing import List
from utilities import SNSHelper, SESHelper, EmailManager, Configuration


class NotificationService:

    def __init__(self):
        self.email_manager = EmailManager()
        self.configuration = Configuration().get_config()
        self.sns_helper = None
        self.ses_helper = None

        if not self.configuration.isLocal:
            self.sns_helper = SNSHelper(
                self.configuration.notificationTopicName,
                self.configuration.snsArnSecretName
            )

            self.ses_helper = SESHelper(
                self.configuration.fileProcessingReportSender
            )

    def send_email(self, template_args: dict, email_template_name: str):

        if self.configuration.isLocal:
            return None

        subject, body = self.email_manager.prepare_email(
            template_args,
            email_template_name
        )

        response = self.sns_helper.publish_message(body, subject)

        return response

    def send_email_with_attachment(
        self,
        template_args: dict,
        email_template_name: str,
        recipient_emails: List[str],
        file_name,
        file
    ):

        if self.configuration.isLocal:
            return None

        subject, body = self.email_manager.prepare_email(
            template_args,
            email_template_name
        )

        response = self.ses_helper.send_email(
            recipient_emails,
            subject,
            body,
            file_name,
            file
        )

        return response