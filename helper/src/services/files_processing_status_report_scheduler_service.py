from datetime import datetime, timezone
import logging
import json
from utilities import Configuration, Utility

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class FilesProcessingStatusReportSchedulerService:

    def __init__(self):
        configuration = Configuration().get_config()
        self.processed_report_rule_name = "trigger-file_processing_status_report_scheduler"

        # Initializes the service with necessary AWS parameters and retrieves Lambda ARN from Secrets Manager.
        self.summary_report_rule_name = "trigger-file_summary_report_scheduler"

        # Initializes the service with necessary AWS parameters and retrieves Lambda ARN from Secrets Manager.
        self.eventbridge = Utility.get_boto3_client("events", configuration)
        self.secrets_manager = Utility.get_boto3_client("secretsmanager", configuration)
        self.lambda_client = Utility.get_boto3_client("lambda", configuration)

    def get_lambda_arn_from_secret(self, secret_name):
        """
        Retrieves the Lambda ARN from AWS Secrets Manager.
        """
        try:
            secret_value = self.secrets_manager.get_secret_value(SecretId=secret_name)
            secret = json.loads(secret_value["SecretString"])
            return secret.get("Function-arn", "")
        except Exception as e:
            print(f"Error retrieving secret: {e}")
            return ""

    def schedule_statement_status_report_generation(self, secret_name, attempt_interval, is_process_report, payload):
        """
        Schedules the Lambda to start running as per attempt_interval (in minutes) from now
        and then every attempt_interval minutes.
        """
        rule_name = self.processed_report_rule_name if is_process_report else self.summary_report_rule_name
        lambda_arn = self.get_lambda_arn_from_secret(secret_name)

        # Create EventBridge rule to start after attempt_interval minutes and then repeat every attempt_interval minutes
        response = self.eventbridge.put_rule(
            Name=rule_name,
            ScheduleExpression=self.get_cron_expression(attempt_interval),
            State="ENABLED",
            Description=f"Trigger statement status report generator every {attempt_interval} minutes",
        )

        rule_arn = response["RuleArn"]

        target = {}
        if payload is not None:
            target = [{"Id": "1", "Arn": lambda_arn, "Input": json.dumps(payload)}]
        else:
            target = [{"Id": "1", "Arn": lambda_arn}]

        logger.info(f"event target: {target}")

        # Attach Lambda as target
        self.eventbridge.put_targets(
            Rule=rule_name,
            Targets=target
        )

        try:
            # add permission for lambda
            self.lambda_client.add_permission(
                FunctionName=lambda_arn,
                StatementId="AllowEventBridgeInvoke",
                Action="lambda:InvokeFunction",
                Principal="events.amazonaws.com",
                SourceArn=rule_arn
            )
        except self.lambda_client.exceptions.ResourceConflictException:
            logger.info("Permission already exists")

        return {"status": "Scheduled", "rule_name": rule_name}

    def delete_schedule_rule(self, secret_name, is_process_report):
        """
        Deletes the EventBridge rule and removes all targets.
        """
        rule_name = self.processed_report_rule_name if is_process_report else self.summary_report_rule_name
        lambda_arn = self.get_lambda_arn_from_secret(secret_name)

        try:
            # Remove targets first
            self.eventbridge.remove_targets(Rule=rule_name, Ids=["1"])

            # Delete the rule
            self.eventbridge.delete_rule(Name=rule_name, Force=True)

            # Remove permission from Lambda
            self.lambda_client.remove_permission(
                FunctionName=lambda_arn,
                StatementId="AllowEventBridgeInvoke"
            )

            logger.info(f"Event bridge rule: {rule_name} has been deleted successfully.")
            return {"status": "Deleted", "rule_name": rule_name}

        except Exception as e:
            logger.error(f"Error occurred while deleting Event Bridge rule: {rule_name}, Error: {str(e)}")
            return {"status": "Error", "message": str(e)}

    def get_minutes_from_now(self, interval):
        now = datetime.now(timezone.utc)
        start_minute = now.minute
        minutes = []
        current_minute = start_minute

        while True:
            minutes.append(current_minute)
            current_minute = (current_minute + interval) % 60

            if current_minute == start_minute:
                break

            if current_minute in minutes:
                break

        return sorted(set(minutes))

    def get_cron_expression(self, interval):
        minute_list = self.get_minutes_from_now(interval)
        minutes_str = ",".join(str(minute) for minute in minute_list)
        cron_expression = f"cron({minutes_str} * * * ? *)"
        logger.info(f"Creating eventbridge with cron expression: {cron_expression}")
        return cron_expression