import json
import logging
from services import AssignmentLetterValidationService

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    num_messages = len(event['Records'])
    logger.info(f'Processing {num_messages} messages for assignment letter validation')

    assignment_letter_validation_service = AssignmentLetterValidationService()

    for record in event['Records']:
        list_of_queued_iprs_str = record['body']
        list_of_queued_iprs = json.loads(list_of_queued_iprs_str)

        request_id = assignment_letter_validation_service.validate(list_of_queued_iprs)

        if request_id:
            logger.info(
                f'Assignment letter request {request_id} has been queued for submission.'
            )

    return {
        'statusCode': 200,
        'body': json.dumps('Assignment letter validation has finished.')
    }
