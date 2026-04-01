import datetime
from collections import defaultdict
from zoneinfo import ZoneInfo
import logging
import http.client
import json
import ssl
import uuid

from repositories import StatementRepository, StatementRequestRepository
from files_processing_status_report_scheduler_service import FilesProcessingStatusReportSchedulerService
from utilities import Utility, SQSHelper, Configuration, SecretManager
from notification_service import NotificationService

log = logging.getLogger()
log.setLevel(logging.INFO)


class FilesProcessingSummaryReportService:

    def __init__(self):
        self.configuration = Configuration().get_config()
        self.opentext_endpoint = SecretManager.get_opentext_endpoint() if not self.configuration.isLocal else None
        self.statement_repository = StatementRepository()
        self.statement_request_repository = StatementRequestRepository()
        self.notification_service = NotificationService()
        self.consolidated_ipr_status_list = []
        self.file_processing_status_report_scheduler_service = FilesProcessingStatusReportSchedulerService()
        self.sqs_helper = SQSHelper(self.configuration.requestQueueName, self.configuration.integrationConfigSecretName)
        self.submission_id = None
        self.statements_queue_name = self.configuration.statementsQueueName
        self.integrationConfigSecretName = self.configuration.integrationConfigSecretName

    def send_report(self, submission_id):
        log.info(f"Calling send_report to generate summary report for submission_id {submission_id}...")
        self.submission_id = submission_id

        message_count = self.sqs_helper.get_sqs_message_count()
        if message_count and message_count > 0:
            log.info("System is still processing statement requests.")
            return "System is still processing statement requests."

        today = datetime.date.today()
        total_statements_in_aws = self.statement_repository.get_statement_count_by_date(today, self.submission_id)
        log.info(f"Total expected statement in aws: {total_statements_in_aws}")

        total_statements_in_opentext = self.get_total_statements_processed_from_opentext()
        log.info(f"Total statements generated in opentext: {total_statements_in_opentext}")

        if total_statements_in_aws == 0:
            log.info("No statement request was submitted.")
            log.info("Deleting trigger for summary report scheduling.")
            self.file_processing_status_report_scheduler_service.delete_schedule_rule(self.configuration.fileSummaryReportScheduleRuleName)
            return f"No statement summary report to be generated as no request was submitted and expected statement is: {total_statements_in_aws}"

        if total_statements_in_aws > total_statements_in_opentext:
            return "OpenText is still processing statement requests"

        log.info("Starting to generate report.")

        report = self.get_report()
        if not report:
            log.info("Could not generate report")
            return

        template_args = {}
        now = datetime.datetime.now(ZoneInfo("Europe/London"))
        template_args['date'] = now.strftime("%Y-%m-%d")
        template_args['time'] = now.strftime("%H-%M")
        template_args['env'] = self.configuration.env
        template_args['run_id'] = str(self.submission_id)

        filename = f"extract_files_summary_report_{template_args['date']}_{template_args['time']}.csv"

        recipient_emails = self.configuration.fileSummaryReportRecipients
        self.notification_service.send_email_with_attachment(template_args, "SUMMARY_REPORT", recipient_emails, report, filename)

        log.info("Deleting trigger for summary report scheduling.")
        self.file_processing_status_report_scheduler_service.delete_schedule_rule(self.configuration.fileSummaryReportScheduleRuleName)

        self.update_statements_for_open_text_response()

        try:
            self.queue_for_statement_update_from_open_text_response()
        except Exception as e:
            log.info(f"Could not queue messages for statement update from OpenText. {e}")

        self.cleanup_opentext()

        return f"A report has been sent successfully to {recipient_emails}"

    def cleanup_opentext(self):
        xml_string = """<Document>
<requestType>cleanup</requestType>
</Document>"""
        base64_encoded_request = self.encode_xml_to_base64_with_padding(xml_string)
        open_text_response = self.get_opentext_response(base64_encoded_request)
        return open_text_response['status']

    def get_total_statements_processed_from_opentext(self):
        total_requests = self.get_total_requests_submitted(self.submission_id)

        xml_string = f"""<Document>
<requestType>totalprocessed</requestType>
<submissionId>{self.submission_id}</submissionId>
<totalRequests>{total_requests}</totalRequests>
</Document>"""

        base64_encoded_request = self.encode_xml_to_base64_with_padding(xml_string)
        open_text_response = self.get_opentext_response(base64_encoded_request)

        try:
            total_records_processed = int(open_text_response['data']['result'][0]['TotalRecordsProcessed'][0])
        except Exception:
            total_records_processed = 0

        return total_records_processed

    def get_request_status_from_opentext(self, request_id):
        xml_string = f"""<Document>
<requestType>statementrequest</requestType>
<statementRequestId>{request_id}</statementRequestId>
<submissionId>{self.submission_id}</submissionId>
</Document>"""

        params = {'request_id': request_id}
        base64_encoded_request = self.encode_xml_to_base64_with_padding(xml_string, params)
        open_text_response = self.get_opentext_response(base64_encoded_request)

        ipr_list = open_text_response['data']['result'][0]['IPR'][0].split(':')
        processing_status = open_text_response['data']['result'][0]['StatementProcessingStatus'][0].split(':')
        reason_of_failure = open_text_response['data']['result'][0]['ReasonForFailure'][0].split(':')

        ipr_status_list = []
        today = datetime.date.today()

        for i in range(len(ipr_list)):
            ipr_status_list.append({
                "IPR": ipr_list[i],
                "Date": today,
                "Statement Processing Status": processing_status[i],
                "Reason for Failure": reason_of_failure[i]
            })

        return ipr_status_list

    def get_opentext_response(self, base64_encoded_request):
        ssl_context = ssl._create_unverified_context()

        payload = json.dumps({
            "content": {
                "contentType": "application/xml",
                "data": base64_encoded_request
            }
        })

        authentication_ticket = self.get_authentication_token()

        headers = {
            "OTDSTICKET": f"{authentication_ticket}",
            "Content-Type": "application/json"
        }

        endpoint_url = self.configuration.opentextRequestUrl if self.configuration.isLocal else self.opentext_endpoint.request_url
        host, path = Utility.extract_host_and_path(endpoint_url)

        conn = http.client.HTTPSConnection(host, context=ssl_context)
        try:
            conn.request("POST", path, payload, headers)
            response = conn.getresponse()

            if response.status >= 400:
                raise Exception(f"Request failed with status {response.status}: {response.reason}")

            response_data = response.read().decode()
            return json.loads(response_data)

        finally:
            conn.close()

    def encode_xml_to_base64_with_padding(self, xml_string, params=None):
        formatted_xml = xml_string.format(**params) if params else xml_string
        return Utility.encode_to_base64_with_padding(formatted_xml)

    def get_report(self):
        self.consolidated_ipr_status_list = self.get_processing_statuses()

        if not self.consolidated_ipr_status_list:
            return None

        field_names = ["IPR", "Date", "Statement Processing Status", "Reason for Failure"]
        self.consolidated_ipr_status_list = sorted(self.consolidated_ipr_status_list, key=lambda x: x["IPR"])

        return Utility.generate_csv(self.consolidated_ipr_status_list, field_names)

    def get_processing_statuses(self):
        today = datetime.date.today()
        statement_request_ids = self.statement_repository.get_distinct_statement_request_id_by_date(today, self.submission_id)

        consolidated_ipr_status_list = []
        if not statement_request_ids:
            return None

        for request_id in statement_request_ids:
            ipr_status_list = self.get_request_status_from_opentext(str(request_id))
            consolidated_ipr_status_list.extend(ipr_status_list)

        return consolidated_ipr_status_list

    def get_authentication_token(self):
        ssl_context = ssl._create_unverified_context()

        if not self.configuration.isLocal:
            username = self.opentext_endpoint.username
            password = self.opentext_endpoint.password
            endpoint_url = self.opentext_endpoint.auth_url
        else:
            username = self.configuration.opentextUsername
            password = self.configuration.opentextPassword
            endpoint_url = self.configuration.opentextAuthUrl

        payload = json.dumps({
            "user_name": username,
            "password": password
        })

        headers = {"Content-Type": "application/json"}

        host, path = Utility.extract_host_and_path(endpoint_url)

        conn = http.client.HTTPSConnection(host, context=ssl_context)
        try:
            conn.request("POST", path, payload, headers)
            response = conn.getresponse()

            if response.status >= 400:
                raise Exception(f"Request failed with status {response.status}: {response.reason}")

            response_data = response.read().decode()
            response_json = json.loads(response_data)

            return response_json.get("ticket")

        finally:
            conn.close()

    def get_total_requests_submitted(self, submission_id):
        total_requests_submitted = self.statement_request_repository.get_total_request_submission(submission_id)
        log.info(f"Total request submitted to OpenText is: {total_requests_submitted}")
        return total_requests_submitted