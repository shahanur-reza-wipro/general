# sqs_helper.py
import logging
import boto3
import json
import os
from botocore.exceptions import ClientError

log = logging.getLogger()


class SQSHelper:

    def __init__(self, sqs_queue_name, sqs_configuration_secret_name=None):
        self.sqs_client = None
        self.sqs_queue_url = None
        self.sqs_queue_name = sqs_queue_name
        self.sqs_configuration_secret_name = sqs_configuration_secret_name

        if not self.sqs_queue_name:
            raise ValueError("SQS queue name is empty. Check resolved configuration values.")

        self.load_configuration()

    def load_configuration(self):
        """Dynamically load AWS SQS configuration"""
        if os.getenv("AWS_EXECUTION_ENV"):  # Running in AWS Lambda
            self.load_from_aws_secrets_manager()
        else:
            self.load_from_env_variables()

    def load_from_env_variables(self):
        """Load AWS SQS credentials from environment variables (for local development)"""
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_session_token = os.getenv(
            "AWS_SESSION_TOKEN"
        )  # Optional for temporary credentials
        region_name = os.getenv("AWS_REGION", "eu-west-2")
        endpoint_url = os.getenv("AWS_ENDPOINT_URL")
        aws_account_id = os.getenv("AWS_ACCOUNT_ID")

        # Build client kwargs dynamically so LocalStack and real AWS both work.
        client_kwargs = {
            "region_name": region_name,
        }

        if endpoint_url:
            client_kwargs["endpoint_url"] = endpoint_url

        if aws_access_key:
            client_kwargs["aws_access_key_id"] = aws_access_key

        if aws_secret_key:
            client_kwargs["aws_secret_access_key"] = aws_secret_key

        if aws_session_token:
            client_kwargs["aws_session_token"] = aws_session_token

        # Initialize Boto3 SQS Client using environment variables/default credential chain
        self.sqs_client = boto3.client("sqs", **client_kwargs)

        # LocalStack path: resolve queue URL by queue name via endpoint.
        if endpoint_url:
            self.sqs_queue_url = self._resolve_queue_url_by_name(self.sqs_queue_name)
            return

        # Real AWS local/dev path: construct queue URL from account + queue name.
        if not aws_account_id:
            raise Exception("Missing AWS_ACCOUNT_ID in environment variables!")

        self.sqs_queue_url = (
            f"https://sqs.{region_name}.amazonaws.com/{aws_account_id}/{self.sqs_queue_name}"
        )

    def _resolve_queue_url_by_name(self, queue_name):
        try:
            response = self.sqs_client.get_queue_url(QueueName=queue_name)
            return response["QueueUrl"]
        except ClientError:
            # Local convenience: if queue does not exist, create it on-demand.
            self.sqs_client.create_queue(QueueName=queue_name)
            response = self.sqs_client.get_queue_url(QueueName=queue_name)
            return response["QueueUrl"]

    def load_from_aws_secrets_manager(self):
        """Fetch SQS credentials from AWS Secrets Manager (used in production)"""
        secrets_manager_client = boto3.client("secretsmanager")
        if self.sqs_configuration_secret_name:
            response = secrets_manager_client.get_secret_value(
                SecretId=self.sqs_configuration_secret_name
            )
            secret_data = json.loads(response["SecretString"])
            self.sqs_queue_url = secret_data.get(self.sqs_queue_name)

        # Initialize SQS Client using IAM role credentials (automatically detected)
        self.sqs_client = boto3.client("sqs")

    def send_message(self, message_body):
        """Sends a message to SQS"""
        response = self.sqs_client.send_message(
            QueueUrl=self.sqs_queue_url,
            MessageBody=message_body,
        )
        return response

    def receive_messages(self, max_messages=10):
        """Receive messages from SQS"""
        response = self.sqs_client.receive_message(
            QueueUrl=self.sqs_queue_url,
            MaxNumberOfMessages=max_messages,
            WaitTimeSeconds=10,  # Long polling
        )
        return response.get("Messages", [])

    def delete_message(self, receipt_handle):
        """Delete a message from SQS"""
        self.sqs_client.delete_message(
            QueueUrl=self.sqs_queue_url,
            ReceiptHandle=receipt_handle,
        )

    def get_sqs_message_count(self):
        try:
            response = self.sqs_client.get_queue_attributes(
                QueueUrl=self.sqs_queue_url,
                AttributeNames=[
                    "ApproximateNumberOfMessages",
                    "ApproximateNumberOfMessagesNotVisible",
                ],
            )
            if response:
                available_messages = int(
                    response["Attributes"].get("ApproximateNumberOfMessages", 0)
                )
                in_flight_messages = int(
                    response["Attributes"].get(
                        "ApproximateNumberOfMessagesNotVisible", 0
                    )
                )
                total_messages = available_messages + in_flight_messages
                log.info(f"Total message in the queue is: {total_messages}")
                return total_messages
        except Exception as e:
            log.error(f"Error retrieving SQS queue attributes {str(e)}")
            return None