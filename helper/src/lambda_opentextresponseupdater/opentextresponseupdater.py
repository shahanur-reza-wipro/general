import json
import logging
from services import StatementResponseService

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    num_messages = len(event['Records'])
    logger.info(f'Processing {num_messages} messages')

    statement_response_service = StatementResponseService()
    results = []

    for record in event['Records']:
        logger.info(f'data received: {record["body"]}')

        data = json.loads(record['body'])
        submission_id = data['submission_id']
        ipr_status_list = data['ipr_status_list']

        result = statement_response_service.update_statements_for_open_text_response(
            ipr_status_list,
            submission_id
        )

        results.append(result)

    # Return a success message
    return {
        'statusCode': 200,
        'body': json.dumps(results)
    }