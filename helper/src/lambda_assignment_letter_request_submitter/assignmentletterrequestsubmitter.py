import asyncio
import json
import logging
from services import AssignmentLetterSubmissionService

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    num_messages = len(event['Records'])
    logger.info(f'Processing {num_messages} assignment letter submission messages')

    assignment_letter_submission_service = AssignmentLetterSubmissionService()
    results = []

    for record in event['Records']:
        sqs_message = record['body']
        result = asyncio.run(
            assignment_letter_submission_service.submit_to_opentext(sqs_message)
        )
        results.append(result)

    return {
        'statusCode': 200,
        'body': json.dumps(results)
    }
