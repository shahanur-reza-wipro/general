import asyncio
import json
import logging
from services import StatementRequestSubmissionService

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    num_messages = len(event['Records'])
    logger.info(f'Processing {num_messages} messages')

    statement_request_submission_service = StatementRequestSubmissionService()
    loop = asyncio.get_event_loop()
    results = []

    for record in event['Records']:
        opentext_request = record['body']
        result = loop.run_until_complete(
            statement_request_submission_service.submit_to_opentext(opentext_request)
        )
        results.append(result)

    # Return a success message
    return {
        'statusCode': 200,
        'body': json.dumps(results)
    }