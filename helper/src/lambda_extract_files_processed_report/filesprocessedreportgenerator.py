from services import FilesProcessingStatusReportService
import logging

log = logging.getLogger()


def lambda_handler(event, context):
    log.info(f'event received {event}')

    submission_id = event.get("submission_id")
    log.info(f'submission id: {submission_id}')

    files_processing_status_report_service = FilesProcessingStatusReportService()

    result = files_processing_status_report_service.send_report(submission_id)

    return {
        'statusCode': 200,
        'body': result
    }