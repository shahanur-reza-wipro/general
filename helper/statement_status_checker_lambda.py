import boto3
import json
from datetime import datetime, timedelta

eventbridge = boto3.client('events')

# Define ARNs
CHECKER_LAMBDA_ARN = "arn:aws:lambda:<region>:<account_id>:function:<checker_lambda_name>"

def schedule_checker_lambda():
    # Calculate execution time (5 minutes from now)
    scheduled_time = (datetime.utcnow() + timedelta(minutes=5)).isoformat() + "Z"

    # Unique rule name (using timestamp for uniqueness)
    rule_name = f"trigger-checker-{int(datetime.utcnow().timestamp())}"

    # Create EventBridge rule
    eventbridge.put_rule(
        Name=rule_name,
        ScheduleExpression=f"at({scheduled_time})",
        State="ENABLED",
        Description="Trigger SQS checker Lambda after 5 minutes",
    )

    # Set the rule to invoke the Lambda function
    eventbridge.put_targets(
        Rule=rule_name,
        Targets=[{"Id": "1", "Arn": CHECKER_LAMBDA_ARN}]
    )

    return {"status": "Scheduled checker Lambda", "rule_name": rule_name}

def lambda_handler(event, context):
    # Your existing logic for queueing messages here

    # Schedule the checker Lambda
    response = schedule_checker_lambda()
    
    return response
