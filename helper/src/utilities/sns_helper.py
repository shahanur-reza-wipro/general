import boto3
import json
import os
import logging
from botocore.exceptions import BotoCoreError, NoCredentialsError

logging.basicConfig(level=logging.INFO)


class SNSHelper:

    def __init__(self, sns_topic_name, sns_configuration_secret_name=None):
        """Initialize SNSHelper based on environment (Lambda or Local)."""
        self.sns_client = None
        self.sns_topic_arn = None
        self.sns_topic_name = sns_topic_name
        self.sns_configuration_secret_name = sns_configuration_secret_name

        self.load_configuration()

    def load_configuration(self):
        """Dynamically load AWS SNS configuration."""
        if os.getenv("AWS_EXECUTION_ENV"):  # Running in AWS Lambda
            self.load_from_aws_secrets_manager()
        else:
            self.load_from_env_variables()

    def load_from_env_variables(self):
        """Load AWS SNS credentials from environment variables (for local development)."""
        aws_access_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY")
        aws_session_token = os.getenv(
            "AWS_SESSION_TOKEN"
        )  # Optional for temporary credentials
        region_name = os.getenv("AWS_REGION", "eu-west-2")
        aws_account_id = os.getenv("AWS_ACCOUNT_ID")

        # Construct SNS Topic ARN
        self.sns_topic_arn = (
            f"arn:aws:sns:{region_name}:{aws_account_id}:{self.sns_topic_name}"
        )

        if not aws_access_key or not aws_secret_key or not self.sns_topic_arn:
            raise Exception(
                "❌ Missing AWS credentials or SNS topic ARN in environment variables!"
            )

        # Initialize Boto3 SNS Client using environment variables
        self.sns_client = boto3.client(
            "sns",
            aws_access_key_id=aws_access_key,
            aws_secret_access_key=aws_secret_key,
            aws_session_token=aws_session_token,  # Include session token if using temporary credentials
            region_name=region_name,
        )

    def load_from_aws_secrets_manager(self):
        """Fetch SNS Topic ARN from AWS Secrets Manager (used in AWS Lambda)"""
        secrets_manager_client = boto3.client("secretsmanager")

        if self.sns_configuration_secret_name:
            try:
                response = secrets_manager_client.get_secret_value(
                    SecretId=self.sns_configuration_secret_name
                )
                secret_data = json.loads(response["SecretString"])
                self.sns_topic_arn = secret_data.get(self.sns_topic_name)
            except Exception as e:
                logging.error(
                    f"❌ Failed to retrieve SNS ARN from Secrets Manager: {e}"
                )
                raise Exception("❌ Could not retrieve SNS ARN from Secrets Manager")

        if not self.sns_topic_arn:
            raise Exception("❌ SNS Topic ARN not found in Secrets Manager!")

        # Initialize SNS Client using IAM role credentials (automatically detected in Lambda)
        self.sns_client = boto3.client("sns")

    def publish_message(self, message_body, subject="SNS Notification"):
        """Publish a message to the SNS topic"""
        if not self.sns_topic_arn:
            logging.error("❌ SNS Topic ARN is not set.")
            return None

        try:
            response = self.sns_client.publish(
                TopicArn=self.sns_topic_arn,
                Message=message_body,
                Subject=subject,
            )
            logging.info(f"📨 Message sent to SNS: {response['MessageId']}")
            return response["MessageId"]
        except (BotoCoreError, NoCredentialsError) as e:
            logging.error(f"❌ Error publishing message to SNS: {e}")
            return None

    def subscribe_email(self, email):
        """Subscribe an email address to the SNS topic"""
        try:
            response = self.sns_client.subscribe(
                TopicArn=self.sns_topic_arn,
                Protocol="email",
                Endpoint=email,
            )
            logging.info(f"📧 Email {email} subscribed successfully!")
            return response["SubscriptionArn"]
        except Exception as e:
            logging.error(f"❌ Error subscribing email to SNS: {e}")
            return None

    def list_subscriptions(self):
        """List all subscriptions for the SNS topic"""
        try:
            response = self.sns_client.list_subscriptions_by_topic(
                TopicArn=self.sns_topic_arn
            )
            return response.get("Subscriptions", [])
        except Exception as e:
            logging.error(f"❌ Error listing SNS subscriptions: {e}")
            return []


# Example Usage
# if __name__ == "__main__":
#     sns_helper = SNSHelper(sns_topic_name="MySNSTopic")
#
#     # Send SNS message
#     response = sns_helper.publish_message("Hello, this is a test SNS message!", "Test Subject")
#     print(f"SNS Message ID: {response}")
#
#     # Subscribe an email
#     email_subscription = sns_helper.subscribe_email("test@example.com")
#     print(f"Subscription ARN: {email_subscription}")
#
#     # List subscriptions
#     subscriptions = sns_helper.list_subscriptions()
#     print(f"Subscriptions: {subscriptions}")