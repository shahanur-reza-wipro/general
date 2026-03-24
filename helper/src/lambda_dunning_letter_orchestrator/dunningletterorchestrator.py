import json
import logging

from services import DunningLetterValidationService

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)


def lambda_handler(event, context):
    num_messages = len(event['Records'])
    log.info(f'Processing {num_messages} messages for dunning letter validation')

    dunning_letter_validation_service = DunningLetterValidationService()

    for record in event['Records']:
        list_of_queued_iprs_str = record['body']
        list_of_queued_iprs = json.loads(list_of_queued_iprs_str)

        request_id = dunning_letter_validation_service.validate(list_of_queued_iprs)

        if request_id:
            log.info(
                f'Dunning letter request {request_id} has been queued for submission.'
            )

    return {
        'statusCode': 200,
        'body': json.dumps('Dunning letter validation has finished.')
    }
