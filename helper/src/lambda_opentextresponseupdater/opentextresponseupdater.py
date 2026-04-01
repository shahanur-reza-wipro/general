import json
import logging
from services import (
    AssignmentLetterResponseService,
    DunningLetterResponseService,
    StatementResponseService,
)

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event, context):
    num_messages = len(event['Records'])
    logger.info(f'Processing {num_messages} messages')

    statement_response_service = StatementResponseService()
    assignment_letter_response_service = AssignmentLetterResponseService()
    dunning_letter_response_service = DunningLetterResponseService()
    results = []

    for record in event['Records']:
        logger.info(f'data received: {record["body"]}')

        data = json.loads(record['body'])
        document_type = data.get('document_type', 'statement')
        submission_id = data['submission_id']
        ipr_status_list = data['ipr_status_list']

        if document_type == 'assignment':
            result = assignment_letter_response_service.update_assignments_for_open_text_response(
                ipr_status_list,
                submission_id
            )
        elif document_type == 'dunning':
            result = dunning_letter_response_service.update_dunnings_for_open_text_response(
                ipr_status_list,
                submission_id
            )
        else:
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