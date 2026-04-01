import datetime
from zoneinfo import ZoneInfo
import logging
import http.client
import json
import ssl
import uuid

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

        # Keep assignment/dunning independent from statement IDs.
        # If their date-based lookup returns nothing, use only the explicit run ID passed
        # into this summary flow (if available).
        if not assignment_ids and statement_submission_id:
            assignment_ids = [str(statement_submission_id)]

        if not dunning_ids and statement_submission_id:
            dunning_ids = [str(statement_submission_id)]

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
            self.queue_for_assignment_update_from_open_text_response()
            self.queue_for_dunning_update_from_open_text_response()
        except Exception:
            log.info("Could not queue messages for OpenText response update.")

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
            count = self.statement_repository.get_statement_count_by_date(today, sid)
            if count == 0:
                count = self.statement_repository.get_statement_count_by_submission_id(sid)
            statement_total += count

        for sid in self._get_submission_ids("assignment"):
            count = self.assignment_letter_repository.get_assignment_letter_count_by_date(today, sid)
            if count == 0:
                count = self.assignment_letter_repository.get_assignment_letter_count_by_submission_id(sid)
            assignment_total += count

        for sid in self._get_submission_ids("dunning"):
            count = self.dunning_letter_repository.get_dunning_letter_count_by_date(today, sid)
            if count == 0:
                count = self.dunning_letter_repository.get_dunning_letter_count_by_submission_id(sid)
            dunning_total += count

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

        request_type = "totalProcessed"
        endpoint_url = self.get_report_endpoint_url(document_type)

        xml_string = f"""
        <Document>
            <requestType>{request_type}</requestType>
            <submissionId>{submission_id}</submissionId>
            <totalRequests>{total_requests}</totalRequests>
        </Document>
        """

        base64_encoded_request = self.encode_xml_to_base64_with_padding(xml_string)

        log.info(
            f"Fetching total processed from OpenText for {document_type}: "
            f"requestType={request_type}, submissionId={submission_id}, "
            f"totalRequests={total_requests}, endpoint={endpoint_url}"
        )

        open_text_response = self.get_opentext_response(
            base64_encoded_request,
            endpoint_url,
        )

        try:
            total_records_processed = self.extract_total_records_processed(open_text_response)
        except (KeyError, ValueError, TypeError):
            log.info(
                f"OpenText has not processed {document_type} yet or returned an unexpected "
                f"totalProcessed payload. response={open_text_response}"
            )
            total_records_processed = 0
        except Exception as e:
            log.exception(f"Unexpected error while getting {document_type} count: {e}")
            total_records_processed = 0

        return total_records_processed

    def extract_total_records_processed(self, open_text_response):
        data = open_text_response.get("data", {}) if isinstance(open_text_response, dict) else {}
        result = data.get("result", [])

        if isinstance(result, dict):
            result = [result]

        if not isinstance(result, list) or not result:
            raise KeyError("Missing result payload")

        candidate_keys = [
            "TotalRecordsProcessed",
            "totalRecordsProcessed",
            "TotalProcessed",
            "totalProcessed",
            "RecordCount",
            "recordCount",
        ]

        for entry in result:
            if not isinstance(entry, dict):
                continue

            for key in candidate_keys:
                if key not in entry:
                    continue

                value = entry.get(key)

                if isinstance(value, list):
                    value = value[0] if value else 0

                if isinstance(value, dict):
                    nested = value.get("value")
                    if nested is not None:
                        value = nested

                return int(value)

        raise KeyError("Total records processed key not found")

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

    def _with_cache_buster(self, endpoint_url):
        from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

        request_nonce = uuid.uuid4().hex
        parsed_url = urlparse(endpoint_url)
        query_params = parse_qsl(parsed_url.query, keep_blank_values=True)
        query_params.append(("_cb", request_nonce))
        refreshed_url = urlunparse(parsed_url._replace(query=urlencode(query_params)))

        return refreshed_url, request_nonce

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

        refreshed_endpoint_url, request_nonce = self._with_cache_buster(endpoint_url)

        authentication_ticket = self.get_authentication_token()

        headers = {
            "OTDSTicket": f"{authentication_ticket}",
            "Content-Type": "application/json",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0",
            "X-Request-Id": request_nonce,
            "X-Request-Timestamp": datetime.datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
        }

        host, path = Utility.extract_host_and_path(refreshed_endpoint_url)

        log.info(
            f"Sending fresh OpenText request with nonce={request_nonce} to endpoint={refreshed_endpoint_url}"
        )

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
                if not request_ids:
                    request_ids = self.statement_repository.get_distinct_statement_request_id_by_submission_id(
                        sid,
                    )
            elif document_type == "assignment":
                request_ids = self.assignment_letter_repository.get_distinct_assignment_request_id_by_date(
                    today,
                    sid,
                )
                if not request_ids:
                    request_ids = self.assignment_letter_repository.get_distinct_assignment_request_id_by_submission_id(
                        sid,
                    )
            else:
                request_ids = self.dunning_letter_repository.get_distinct_dunning_request_id_by_date(
                    today,
                    sid,
                )
                if not request_ids:
                    request_ids = self.dunning_letter_repository.get_distinct_dunning_request_id_by_submission_id(
                        sid,
                    )

            if request_ids:
                all_request_ids.extend([str(item[0]) for item in request_ids if item and item[0]])

        return list(dict.fromkeys(all_request_ids))

    def get_request_type_for_document(self, document_type):
        mapping = {
            "statement": "statementrequest",
            "assignment": "assignmentrequest",
            "dunning": "dunningrequest",
        }
        return mapping.get(document_type, "statementrequest")

    def get_request_id_tag_for_document(self, document_type):
        mapping = {
            "statement": "statementRequestId",
            "assignment": "assignmentRequestId",
            "dunning": "dunningRequestId",
        }
        return mapping.get(document_type, "statementRequestId")

    def get_request_status_from_opentext(self, request_id, document_type):
        request_type = self.get_request_type_for_document(document_type)
        request_id_tag = self.get_request_id_tag_for_document(document_type)

        xml_string = f"""
        <Document>
            <requestType>{request_type}</requestType>
            <{request_id_tag}>{request_id}</{request_id_tag}>
            <submissionId>{self.report_run_id}</submissionId>
        </Document>
        """

        base64_encoded_request = self.encode_xml_to_base64_with_padding(xml_string)

        open_text_response = self.get_opentext_response(
            base64_encoded_request,
            self.get_report_endpoint_url(document_type),
        )

        return self.parse_request_status_response(open_text_response, document_type)

    def parse_request_status_response(self, open_text_response, document_type):
        response_items = (
            open_text_response.get("data", {}).get("result", [])
            if isinstance(open_text_response, dict)
            else []
        )

        if not response_items:
            return []

        first_result = response_items[0] if isinstance(response_items[0], dict) else {}
        if not first_result:
            return []

        ipr_values = self._extract_colon_values_from_keys(
            first_result,
            ["IPR"],
        )
        if not ipr_values:
            return []

        status_keys_by_type = {
            "statement": ["StatementProcessingStatus"],
            "assignment": ["AssignmentProcessingStatus"],
            "dunning": ["DunningProcessingStatus"],
        }
        fallback_status_keys = ["DocumentProcessingStatus", "documentProcessingStatus", "ProcessingStatus", "processingStatus"]
        status_values = self._extract_colon_values_from_keys(
            first_result,
            status_keys_by_type.get(document_type, []) + fallback_status_keys,
        )

        reason_keys_by_type = {
            "statement": ["ReasonForFailure"],
            "assignment": ["AssignmentFailureReason"],
            "dunning": ["DunningFailureReason"],
        }
        reason_values = self._extract_colon_values_from_keys(
            first_result,
            reason_keys_by_type.get(document_type, []),
        )

        normalized = []
        for index, raw_ipr in enumerate(ipr_values):
            ipr = self.normalize_ipr(raw_ipr)
            if not ipr:
                continue

            processing_status = status_values[index] if index < len(status_values) else ""
            reason_for_failure = reason_values[index] if index < len(reason_values) else ""

            normalized.append(
                {
                    "IPR": ipr,
                    "status": self.normalize_processing_status(processing_status),
                    "reason": reason_for_failure,
                }
            )

        return normalized

    def _extract_colon_values_from_keys(self, item, candidate_keys):
        for key in candidate_keys:
            if key not in item:
                continue
            return self._split_colon_values(item.get(key))
        return []

    def _split_colon_values(self, raw_value):
        if raw_value is None:
            return []

        if isinstance(raw_value, list):
            raw_value = raw_value[0] if raw_value else ""

        if isinstance(raw_value, dict):
            raw_value = raw_value.get("value", "")

        if raw_value is None:
            return []

        text = str(raw_value)
        return [segment.strip() for segment in text.split(":")]

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

    def queue_for_assignment_update_from_open_text_response(self):
        assignment_submission_ids = self._get_submission_ids("assignment")
        assignment_submission_id = assignment_submission_ids[0] if assignment_submission_ids else ""
        if not assignment_submission_id:
            return None

        assignment_rows = []
        for row in self.consolidated_ipr_status_list:
            if Utility.is_none_or_empty(row.get("Assignment Processing Status")):
                continue
            assignment_rows.append(
                {
                    "IPR": row.get("IPR"),
                    "Assignment Processing Status": row.get("Assignment Processing Status"),
                    "Reason For Failure": row.get("Assignment Failure Reason"),
                }
            )

        if not assignment_rows:
            return None

        chunked_responses = Utility.chunk_data(assignment_rows, 100)

        for response in chunked_responses:
            sqs_message_body = {
                "document_type": "assignment",
                "submission_id": str(assignment_submission_id),
                "ipr_status_list": response,
            }

            self.assignment_requests_sqs_helper.send_message(
                json.dumps(sqs_message_body, default=Utility.json_serializer)
            )

        log.info(
            f"{len(assignment_rows)} IPRs have been queued for assignment update from OpenText response."
        )

        return None

    def queue_for_dunning_update_from_open_text_response(self):
        dunning_submission_ids = self._get_submission_ids("dunning")
        dunning_submission_id = dunning_submission_ids[0] if dunning_submission_ids else ""
        if not dunning_submission_id:
            return None

        dunning_rows = []
        for row in self.consolidated_ipr_status_list:
            if Utility.is_none_or_empty(row.get("Dunning Processing Status")):
                continue
            dunning_rows.append(
                {
                    "IPR": row.get("IPR"),
                    "Dunning Processing Status": row.get("Dunning Processing Status"),
                    "Reason For Failure": row.get("Dunning Failure Reason"),
                }
            )

        if not dunning_rows:
            return None

        chunked_responses = Utility.chunk_data(dunning_rows, 100)

        for response in chunked_responses:
            sqs_message_body = {
                "document_type": "dunning",
                "submission_id": str(dunning_submission_id),
                "ipr_status_list": response,
            }

            self.dunning_requests_sqs_helper.send_message(
                json.dumps(sqs_message_body, default=Utility.json_serializer)
            )

        log.info(
            f"{len(dunning_rows)} IPRs have been queued for dunning update from OpenText response."
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