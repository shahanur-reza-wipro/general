import datetime
from zoneinfo import ZoneInfo
import logging
import http.client
import json
import ssl

from repositories import (
    StatementRepository,
    StatementRequestRepository,
    AssignmentLetterRepository,
    AssignmentLetterRequestRepository,
    DunningLetterRepository,
    DunningLetterRequestRepository,
)
from .files_processing_status_report_scheduler_service import FilesProcessingStatusReportSchedulerService
from utilities import Utility, SQSHelper, Configuration, SecretManager
from .notification_service import NotificationService

log = logging.getLogger()
log.setLevel(logging.INFO)


class FilesProcessingSummaryReportService:

    STATUS_RANK = {
        "Generated Emailed": 1,
        "Generated Not Emailed": 2,
        "Not Generated": 3,
    }

    def __init__(self):

        self.configuration = Configuration().get_config()

        self.opentext_endpoint = (
            SecretManager().get_opentext_endpoint() if not self.configuration.isLocal else None
        )

        self.statement_repository = StatementRepository()
        self.statement_request_repository = StatementRequestRepository()
        self.assignment_letter_repository = AssignmentLetterRepository()
        self.assignment_letter_request_repository = AssignmentLetterRequestRepository()
        self.dunning_letter_repository = DunningLetterRepository()
        self.dunning_letter_request_repository = DunningLetterRequestRepository()

        self.notification_service = NotificationService()

        self.consolidated_ipr_status_list = []

        self.file_processing_status_report_scheduler_service = FilesProcessingStatusReportSchedulerService()

        self.statement_requests_sqs_helper = SQSHelper(
            self.configuration.requestsQueueName,
            self.configuration.integrationConfigSecretName,
        )
        self.assignment_requests_sqs_helper = SQSHelper(
            self.configuration.assignmentLetterRequestsQueueName,
            self.configuration.integrationConfigSecretName,
        )
        self.dunning_requests_sqs_helper = SQSHelper(
            self.configuration.dunningLetterRequestsQueueName,
            self.configuration.integrationConfigSecretName,
        )

        self.report_run_id = ""
        self.submission_ids_by_type = {
            "statement": [],
            "assignment": [],
            "dunning": [],
        }
        self.statements_queue_name = self.configuration.statementsQueueName
        self.integration_config_secret_name = self.configuration.integrationConfigSecretName

    def _normalize_submission_id_rows(self, rows):
        normalized = []
        for row in rows or []:
            value = row[0] if isinstance(row, (list, tuple)) else row
            if value:
                normalized.append(str(value))
        return normalized

    def _resolve_submission_ids(self, statement_submission_id, request_date):
        statement_ids = [str(statement_submission_id)] if statement_submission_id else []

        assignment_ids = self._normalize_submission_id_rows(
            self.assignment_letter_request_repository.get_distinct_submission_ids_by_date(request_date)
        )
        dunning_ids = self._normalize_submission_id_rows(
            self.dunning_letter_request_repository.get_distinct_submission_ids_by_date(request_date)
        )

        # Preserve original behavior for statements while still supporting date-based fallback.
        if not statement_ids:
            statement_ids = self._normalize_submission_id_rows(
                self.statement_request_repository.get_distinct_submission_ids_by_date(request_date)
            )

        return {
            "statement": statement_ids,
            "assignment": assignment_ids,
            "dunning": dunning_ids,
        }

    def _get_submission_ids(self, document_type):
        return self.submission_ids_by_type.get(document_type, [])

    def send_report(self, submission_id):

        log.info(
            f"Calling send_report to generate summary report for submission_id {submission_id}..."
        )

        self.report_run_id = str(submission_id) if submission_id else ""
        self.submission_ids_by_type = self._resolve_submission_ids(self.report_run_id, datetime.date.today())

        pending_messages = self.get_total_pending_request_messages()
        log.info(f"Pending messages by type: {pending_messages}")
        still_pending = [doc_type for doc_type, count in pending_messages.items() if count > 0]
        if still_pending:
            for doc_type in still_pending:
                log.info(f"{pending_messages[doc_type]} pending {doc_type} request(s) still in queue.")
            return f"System is still processing requests for: {', '.join(still_pending)}."

        today = datetime.date.today()

        total_documents_in_aws = self.get_total_documents_in_aws(today)
        log.info(f"Total documents in aws by type: {total_documents_in_aws}")

        if sum(total_documents_in_aws.values()) == 0:
            log.info("No statement / assignment / dunning request was submitted.")
            log.info("Deleting trigger for summary report scheduling.")

            self.file_processing_status_report_scheduler_service.delete_schedule_rule(
                self.configuration.integrationConfigSecretName,
                False,
            )

            return (
                "No summary report to be generated as no statement / assignment / "
                "dunning request was submitted."
            )

        for doc_type, aws_total in total_documents_in_aws.items():
            if aws_total == 0:
                log.info(f"No {doc_type} requests submitted, skipping OpenText check.")
                continue
            opentext_total = self.get_total_processed_for_document_type(doc_type)
            log.info(f"Total {doc_type} documents processed in OpenText: {opentext_total}")
            if aws_total > opentext_total:
                return f"OpenText is still processing {doc_type} requests."

        log.info("Starting to generate report.")

        report = self.get_report()

        if not report:
            log.info("could not generate report")
            return

        template_args = {}

        now = datetime.datetime.now(ZoneInfo("Europe/London"))

        template_args["date"] = now.strftime("%Y-%m-%d")
        template_args["time"] = now.strftime("%H-%M")
        template_args["env"] = self.configuration.env
        template_args["run_id"] = str(self.report_run_id)

        filename = f"extract_summary_report{template_args['date']}_{template_args['time']}.csv"

        recipient_emails = self.configuration.fileSummaryReportRecipients

        self.notification_service.send_email_with_attachment(
            template_args,
            "SUMMARY_REPORT",
            filename,
            report,
            recipient_emails,
        )

        log.info("Deleting trigger for summary report scheduling.")

        self.file_processing_status_report_scheduler_service.delete_schedule_rule(
            self.configuration.integrationConfigSecretName,
            False,
        )

        log.info(f"A report has been sent successfully to {recipient_emails}")

        try:
            self.queue_for_statement_update_from_open_text_response()
        except Exception:
            log.info("Could not queue messages for statement update from OpenText.")

        self.cleanup_opentext()

        return f"A report has been sent successfully to {recipient_emails}"

    def get_total_pending_request_messages(self):
        statement_pending = self.statement_requests_sqs_helper.get_sqs_message_count() or 0
        assignment_pending = self.assignment_requests_sqs_helper.get_sqs_message_count() or 0
        dunning_pending = self.dunning_requests_sqs_helper.get_sqs_message_count() or 0
        return {
            "statement": statement_pending,
            "assignment": assignment_pending,
            "dunning": dunning_pending,
        }

    def cleanup_opentext(self):

        xml_string = """
        <Document>
            <requestType>cleanup</requestType>
        </Document>
        """

        base64_encoded_request = self.encode_xml_to_base64_with_padding(xml_string)

        open_text_response = self.get_opentext_response(
            base64_encoded_request,
            self.get_report_endpoint_url("statement"),
        )

        return open_text_response.get("status")

    def get_total_documents_in_aws(self, today):
        statement_total = 0
        assignment_total = 0
        dunning_total = 0

        for sid in self._get_submission_ids("statement"):
            statement_total += self.statement_repository.get_statement_count_by_date(today, sid)

        for sid in self._get_submission_ids("assignment"):
            assignment_total += self.assignment_letter_repository.get_assignment_letter_count_by_date(today, sid)

        for sid in self._get_submission_ids("dunning"):
            dunning_total += self.dunning_letter_repository.get_dunning_letter_count_by_date(today, sid)

        return {
            "statement": statement_total,
            "assignment": assignment_total,
            "dunning": dunning_total,
        }

    def get_total_documents_processed_from_opentext(self):
        totals = {}

        totals["statement"] = self.get_total_processed_for_document_type("statement")
        totals["assignment"] = self.get_total_processed_for_document_type("assignment")
        totals["dunning"] = self.get_total_processed_for_document_type("dunning")

        return totals

    def get_total_processed_for_document_type(self, document_type):
        total_processed = 0

        for sid in self._get_submission_ids(document_type):
            total_requests = self.get_total_requests_submitted(document_type, sid)
            total_processed += self.get_total_processed_from_opentext(
                document_type,
                total_requests,
                sid,
            )

        return total_processed

    def get_total_processed_from_opentext(self, document_type, total_requests, submission_id):

        if total_requests == 0 or not submission_id:
            return 0

        xml_string = f"""
        <Document>
            <requestType>totalProcessed</requestType>
            <submissionId>{submission_id}</submissionId>
            <totalRequests>{total_requests}</totalRequests>
        </Document>
        """

        base64_encoded_request = self.encode_xml_to_base64_with_padding(xml_string)

        open_text_response = self.get_opentext_response(
            base64_encoded_request,
            self.get_report_endpoint_url(document_type),
        )

        try:
            total_records_processed = int(
                open_text_response["data"]["result"][0]["TotalRecordsProcessed"][0]
            )
        except KeyError:
            log.info(f"OpenText has not processed {document_type} yet")
            total_records_processed = 0
        except Exception as e:
            log.exception(f"Unexpected error while getting {document_type} count: {e}")
            total_records_processed = 0

        return total_records_processed

    def get_report_endpoint_url(self, document_type):
        if document_type == "statement":
            return (
                self.configuration.opentextRequestUrl
                if self.configuration.isLocal
                else self.opentext_endpoint.requestURL
            )

        if document_type == "assignment":
            if self.configuration.isLocal:
                return self.configuration.opentextAssignmentReportUrl
            return (
                getattr(self.opentext_endpoint, "assignment_request_url", None)
                or self.configuration.opentextAssignmentReportUrl
            )

        if self.configuration.isLocal:
            return self.configuration.opentextDunningReportUrl
        return (
            getattr(self.opentext_endpoint, "dunning_request_url", None)
            or self.configuration.opentextDunningReportUrl
        )

    def get_opentext_response(self, base64_encoded_request, endpoint_url):

        ssl_context = ssl._create_unverified_context()

        payload = json.dumps(
            {
                "content": {
                    "contentType": "application/xml",
                    "data": base64_encoded_request,
                }
            }
        )

        authentication_ticket = self.get_authentication_token()

        headers = {
            "OTDSTicket": f"{authentication_ticket}",
            "Content-Type": "application/json",
        }

        host, path = Utility.extract_host_and_path(endpoint_url)

        conn = http.client.HTTPSConnection(host, context=ssl_context)

        try:
            conn.request("POST", path, payload, headers)

            response = conn.getresponse()

            if response.status >= 400:
                raise Exception(
                    f"Request failed with status {response.status}: {response.reason}"
                )

            response_data = response.read().decode()

            return json.loads(response_data)

        finally:
            conn.close()

    def encode_xml_to_base64_with_padding(self, xml_string, params=None):

        formatted_xml = xml_string.format(**params) if params else xml_string

        xml_base64_request = Utility.encode_to_base64_with_padding(formatted_xml)

        return xml_base64_request

    def get_report(self):

        self.consolidated_ipr_status_list = self.get_processing_statuses()

        if not self.consolidated_ipr_status_list:
            return None

        field_names = [
            "IPR",
            "Date",
            "Statement Processing Status",
            "Statement Failure Reason",
            "Assignment Processing Status",
            "Assignment Failure Reason",
            "Dunning Processing Status",
            "Dunning Failure Reason",
        ]

        self.consolidated_ipr_status_list = sorted(
            self.consolidated_ipr_status_list,
            key=lambda x: x["IPR"],
        )

        report = Utility.generate_csv(self.consolidated_ipr_status_list, field_names)

        return report

    def get_processing_statuses(self):

        today = datetime.date.today().strftime("%Y-%m-%d")

        statement_map = self.get_document_status_map("statement")
        assignment_map = self.get_document_status_map("assignment")
        dunning_map = self.get_document_status_map("dunning")

        all_iprs = set(statement_map.keys()) | set(assignment_map.keys()) | set(dunning_map.keys())

        consolidated = []
        for ipr in sorted(all_iprs):
            statement_info = statement_map.get(ipr)
            assignment_info = assignment_map.get(ipr)
            dunning_info = dunning_map.get(ipr)

            statement_status = statement_info["status"] if statement_info else ""
            statement_failure_reason = statement_info["reason"] if statement_info else ""

            row = {
                "IPR": ipr,
                "Date": today,
                "Statement Processing Status": statement_status,
                "Statement Failure Reason": statement_failure_reason,
                "Assignment Processing Status": assignment_info["status"] if assignment_info else "",
                "Assignment Failure Reason": assignment_info["reason"] if assignment_info else "",
                "Dunning Processing Status": dunning_info["status"] if dunning_info else "",
                "Dunning Failure Reason": dunning_info["reason"] if dunning_info else "",
            }

            consolidated.append(row)

        return consolidated

    def get_document_status_map(self, document_type):
        request_ids = self.get_document_request_ids(document_type)
        status_map = {}

        if not request_ids:
            return status_map

        for request_id in request_ids:
            statuses = self.get_request_status_from_opentext(request_id, document_type)
            for status_item in statuses:
                ipr = status_item["IPR"]
                self.merge_status(status_map, ipr, status_item)

        return status_map

    def get_document_request_ids(self, document_type):
        today = datetime.date.today()
        all_request_ids = []

        for sid in self._get_submission_ids(document_type):
            if document_type == "statement":
                request_ids = self.statement_repository.get_distinct_statement_request_id_by_date(
                    today,
                    sid,
                )
            elif document_type == "assignment":
                request_ids = self.assignment_letter_repository.get_distinct_assignment_request_id_by_date(
                    today,
                    sid,
                )
            else:
                request_ids = self.dunning_letter_repository.get_distinct_dunning_request_id_by_date(
                    today,
                    sid,
                )

            if request_ids:
                all_request_ids.extend([str(item[0]) for item in request_ids if item and item[0]])

        return list(dict.fromkeys(all_request_ids))

    def get_request_status_from_opentext(self, request_id, document_type):

        xml_string = f"""
        <Document>
            <requestType>requestStatus</requestType>
            <statementRequestId>{request_id}</statementRequestId>
        </Document>
        """

        base64_encoded_request = self.encode_xml_to_base64_with_padding(xml_string)

        open_text_response = self.get_opentext_response(
            base64_encoded_request,
            self.get_report_endpoint_url(document_type),
        )

        return self.parse_request_status_response(open_text_response)

    def parse_request_status_response(self, open_text_response):
        response_items = (
            open_text_response.get("data", {}).get("result", [])
            if isinstance(open_text_response, dict)
            else []
        )

        if not response_items:
            return []

        first_result = response_items[0] if isinstance(response_items[0], dict) else {}

        ipr_statuses = first_result.get("IPRStatus", [])
        if isinstance(ipr_statuses, dict):
            ipr_statuses = [ipr_statuses]

        normalized = []

        for item in ipr_statuses:
            if not isinstance(item, dict):
                continue

            ipr = self.normalize_ipr(
                item.get("IPR")
                or item.get("ipr")
                or item.get("OpenTextIPR")
                or item.get("openTextIPR")
            )

            if not ipr:
                continue

            processing_status = self.extract_processing_status(item)
            reason_for_failure = self.extract_failure_reason(item)

            normalized.append(
                {
                    "IPR": ipr,
                    "status": self.normalize_processing_status(processing_status),
                    "reason": reason_for_failure,
                }
            )

        return normalized

    def extract_processing_status(self, item):
        status_value = (
            item.get("statementProcessingStatus")
            or item.get("assignmentProcessingStatus")
            or item.get("dunningProcessingStatus")
            or item.get("documentProcessingStatus")
            or item.get("ProcessingStatus")
            or item.get("processingStatus")
        )

        if isinstance(status_value, list):
            return status_value[0] if status_value else None

        return status_value

    def extract_failure_reason(self, item):
        reason = (
            item.get("Reason for Failure")
            or item.get("Reason For Failure")
            or item.get("reasonForFailure")
            or item.get("failureReason")
            or item.get("FailureReason")
        )

        if isinstance(reason, list):
            return reason[0] if reason else ""

        return reason or ""

    def normalize_processing_status(self, status):
        if Utility.is_none_or_empty(status):
            return "Not Generated"

        status_text = str(status).strip()
        lower = status_text.lower()

        if "not generated" in lower:
            return "Not Generated"

        if "generated" in lower and "email" in lower:
            if "not" in lower:
                return "Generated Not Emailed"
            return "Generated Emailed"

        if "failed" in lower or "error" in lower:
            return "Not Generated"

        return status_text

    def normalize_ipr(self, ipr):
        if Utility.is_none_or_empty(ipr):
            return ""
        return str(ipr).replace("/", "").strip()

    def merge_status(self, status_map, ipr, new_item):
        existing = status_map.get(ipr)
        if not existing:
            status_map[ipr] = {
                "status": new_item.get("status", ""),
                "reason": new_item.get("reason", ""),
            }
            return

        current_rank = self.STATUS_RANK.get(existing.get("status"), 0)
        new_rank = self.STATUS_RANK.get(new_item.get("status"), 0)

        if new_rank > current_rank:
            existing["status"] = new_item.get("status", existing.get("status"))
            existing["reason"] = new_item.get("reason") or existing.get("reason")
        elif Utility.is_none_or_empty(existing.get("reason")) and not Utility.is_none_or_empty(new_item.get("reason")):
            existing["reason"] = new_item.get("reason")

        status_map[ipr] = existing

    def queue_for_statement_update_from_open_text_response(self):
        statement_submission_ids = self._get_submission_ids("statement")
        statement_submission_id = statement_submission_ids[0] if statement_submission_ids else ""
        if not statement_submission_id:
            return None

        statement_rows = []
        for row in self.consolidated_ipr_status_list:
            if Utility.is_none_or_empty(row.get("Statement Processing Status")):
                continue
            statement_rows.append(
                {
                    "IPR": row.get("IPR"),
                    "Statement Processing Status": row.get("Statement Processing Status"),
                    "Reason For Failure": row.get("Statement Failure Reason"),
                }
            )

        if not statement_rows:
            return None

        chunked_responses = Utility.chunk_data(statement_rows, 100)

        for response in chunked_responses:

            sqs_message_body = {
                "submission_id": str(statement_submission_id),
                "ipr_status_list": response,
            }

            self.send_to_sqs(
                json.dumps(sqs_message_body, default=Utility.json_serializer)
            )

        log.info(
            f"{len(statement_rows)} IPRs have been queued for statement update from OpenText response."
        )

        return None

    def send_to_sqs(self, message_body):

        sqs_helper = SQSHelper(
            self.statements_queue_name,
            self.integration_config_secret_name,
        )

        queue_response = sqs_helper.send_message(message_body)

        return queue_response

    def update_statements_for_open_text_response(self):

        today = datetime.datetime.now().strftime("%Y-%m-%d")

        statements = []

        for ipr_status in self.consolidated_ipr_status_list:

            ipr = ipr_status["IPR"]

            processing_status = ipr_status.get("Statement Processing Status")

            reason_for_failure = ipr_status.get("Statement Failure Reason")

            statement = self.statement_repository.get_st_by_opentext_ipr_and_date(
                ipr,
                today,
                self.report_run_id,
            )

            if statement is not None:

                if processing_status is not None:
                    statement.StatementProcessingStatus = processing_status

                if reason_for_failure is not None:
                    statement.ReasonForFailure = reason_for_failure

                statements.append(statement)

            else:
                log.info(f"Statement was not found for {self.report_run_id}")

        if statements:
            self.statement_repository.upsert(statements)

    def get_authentication_token(self):

        ssl_context = ssl._create_unverified_context()

        if not self.configuration.isLocal:

            username = self.opentext_endpoint.username
            password = self.opentext_endpoint.password
            endpoint_url = self.opentext_endpoint.auth_url

        else:

            username = self.configuration.opentextUserName
            password = self.configuration.opentextPassword
            endpoint_url = self.configuration.opentextAuthUrl

        payload = json.dumps({"user_name": username, "password": password})

        headers = {"Content-Type": "application/json"}

        host, path = Utility.extract_host_and_path(endpoint_url)

        conn = http.client.HTTPSConnection(host, context=ssl_context)

        try:

            conn.request("POST", path, payload, headers)

            response = conn.getresponse()

            if response.status >= 400:
                raise Exception(
                    f"Request failed with status {response.status}: {response.reason}"
                )

            response_data = response.read().decode()

            response_json = json.loads(response_data)

            return response_json.get("ticket")

        finally:
            conn.close()

    def get_total_requests_submitted(self, document_type, submission_id):
        if not submission_id:
            return 0

        if document_type == "statement":
            return self.statement_request_repository.get_total_request_submission(submission_id)

        if document_type == "assignment":
            return self.assignment_letter_request_repository.get_total_request_submission(submission_id)

        return self.dunning_letter_request_repository.get_total_request_submission(submission_id)