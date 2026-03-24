import asyncio
import json
import logging

from services import DunningLetterSubmissionService

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


def lambda_handler(event, context):
    num_messages = len(event['Records'])
    log.info(f'Processing {num_messages} dunning letter submission messages')

    dunning_letter_submission_service = DunningLetterSubmissionService()
    results = []

    for record in event['Records']:
        sqs_message = record['body']
        result = asyncio.run(
            dunning_letter_submission_service.submit_to_opentext(sqs_message)
        )
        results.append(result)

    return {
        'statusCode': 200,
        'body': json.dumps(results)
    }
