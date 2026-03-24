from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from io import StringIO
from typing import List
import boto3
import json
import os
import logging
from botocore.exceptions import BotoCoreError, NoCredentialsError

logging.basicConfig(level=logging.INFO)


class SESHelper:

    def __init__(self, sender_email):
        self.ses_client = None
        self.sender_email = sender_email
        self.load_configuration()

    def load_configuration(self):
        """Dynamically load AWS SES configuration."""
        if os.getenv("AWS_EXECUTION_ENV"):  # Running in AWS Lambda
            self.load_from_lambda()
        else:
            self.load_from_env_variables()

    def load_from_lambda(self):
        """Initialize SES Client using IAM role credentials (automatically detected in Lambda)"""
        self.ses_client = boto3.client("ses")

    def load_from_env_variables(self):
        """Load AWS SES credentials from environment variables (for local development)."""
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_session_token = os.getenv(
            "AWS_SESSION_TOKEN"
        )  # Optional for temporary credentials
        region_name = os.getenv("AWS_REGION", "eu-west-2")

        if not aws_access_key or not aws_secret_key or not self.sender_email:
            raise Exception(
                "❌ Missing AWS credentials or SES sender email in environment variables!"
            )

        # Initialize Boto3 SES Client using environment variables
        self.ses_client = boto3.client(
            "ses",
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            aws_session_token=aws_session_token,  # Include session token if using temporary credentials
            region_name=region_name,
        )

    def send_email(
        self,
        recipient_emails: List[str],
        subject,
        body,
        attachment_filename: str = None,
        attachment_file: StringIO = None,
    ):
        responses = []
        for recipient_email in recipient_emails:
            response = None
            if attachment_filename:
                response = self.send_email_with_attachment(
                    recipient_email, subject, body, attachment_filename, attachment_file
                )
            else:
                response = self.send_email_non_attachment(
                    self, recipient_email, subject, body
                )
            responses.append(response)
        return responses

    def send_email_with_attachment(
        self,
        recipient_email,
        subject,
        body,
        attachment_filename: str = None,
        attachment_file: StringIO = None,
    ):
        msg = MIMEMultipart()
        msg["Subject"] = subject
        msg["From"] = self.sender_email
        msg["To"] = recipient_email

        msg.attach(MIMEText(body, "plain"))

        if attachment_file is not None:
            file_content = None
            if hasattr(attachment_file, "getvalue"):
                file_content = attachment_file.getvalue()
            else:
                raise ValueError("Unsupported csv_object type. Must be StringIO")

            part = MIMEBase("application", "octet-stream")
            part.set_payload(file_content.encode("utf-8"))
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition", f"attachment; filename={attachment_filename}"
            )
            msg.attach(part)

        try:
            response = self.ses_client.send_raw_email(
                Source=self.sender_email,
                Destinations=[recipient_email],
                RawMessage={"Data": msg.as_string()},
            )
        except Exception as e:
            logging.error(
                f"❌ Failed to send email to {recipient_email}. Error: {e}"
            )
            response = None
        return response

    def send_email_non_attachment(self, recipient_email, subject, body):
        """Send an email using Amazon SES.

        :param recipient_email: The recipient's email address.
        :param subject: The email subject.
        :param body: The email body.
        :return: Response with message ID or an error message.
        """
        if not self.ses_client or not self.sender_email:
            logging.error("❌ SES client or sender email is not set.")
            return None

        try:
            response = self.ses_client.send_email(
                Source=self.sender_email,
                Destination={"ToAddresses": [recipient_email]},
                Message={
                    "Subject": {"Data": subject},
                    "Body": {"Text": {"Data": body}},
                },
            )
            logging.info(f"✅ Email sent successfully: {response['MessageId']}")
            return response["MessageId"]
        except (BotoCoreError, NoCredentialsError) as e:
            logging.error(f"❌ Error sending email via SES: {e}")
            return None

    def is_email_verified(self, email):
        """Check if an email address is verified in SES.

        :param email: The email address to check.
        :return: Boolean indicating if the email is verified.
        """
        try:
            response = self.ses_client.list_verified_email_addresses()
            return email in response.get("VerifiedEmailAddresses", [])
        except Exception as e:
            logging.error(f"❌ Error checking email verification status: {e}")
            return False

    def get_ses_sending_quota(self):
        """Retrieve SES sending quota details.

        :return: Dictionary containing Max24HourSend, MaxSendRate, and SentLast24Hours.
        """
        try:
            response = self.ses_client.get_send_quota()
            return {
                "max_24_hour_send": response["Max24HourSend"],
                "max_send_rate": response["MaxSendRate"],
                "sent_last_24_hours": response["SentLast24Hours"],
            }
        except Exception as e:
            logging.error(f"❌ Error retrieving SES sending quota: {e}")
            return {"error": str(e)}