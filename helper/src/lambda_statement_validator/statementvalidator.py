import json
import logging
from services import StatementValidationService

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    num_messages = len(event['Records'])
    logger.info(f'Processing {num_messages} messages')

    statement_validation_service = StatementValidationService()

    for record in event['Records']:
        list_of_queued_iprs_str = record['body']
        list_of_queued_iprs = json.loads(list_of_queued_iprs_str)

        validation_result = statement_validation_service.validate(list_of_queued_iprs)

        if validation_result:
            request_content, request_id = validation_result
            logger.info(
                f'A request: {request_id} has been queued for statement generation submission.'
            )

    return {
        'statusCode': 200,
        'body': json.dumps('statement validation has been finished')
    }