# assignment_letter_submission_service.py
import asyncio
import http.client
import json
import logging
import ssl

from repositories import AssignmentLetterRepository, AssignmentLetterRequestRepository
from utilities import Configuration, SecretManager, Utility

log = logging.getLogger()


class AssignmentLetterSubmissionService:
    """
    Consumes assignment letter request IDs from SQS, retrieves the persisted
    base64 XML payload, authenticates with OpenText and submits.
    """

    def __init__(self):
        self.configuration = Configuration().get_config()
        self.opentext_endpoint = (
            SecretManager().get_opentext_endpoint()
            if not self.configuration.isLocal
            else None
        )
        self.assignment_letter_repository = AssignmentLetterRepository()
        self.assignment_letter_request_repository = AssignmentLetterRequestRepository()

    # ------------------------------------------------------------------
    # Public entry point (called by lambda)
    # ------------------------------------------------------------------

    async def submit_to_opentext(self, sqs_message: str):
        if not sqs_message:
            return

        request = json.loads(sqs_message)
        request_id = request["request_id"]

        assignment_letter_request = await self._get_request(request_id)

        if not assignment_letter_request:
            log.warning(f"No assignment letter request found for id {request_id}")
            return

        body = assignment_letter_request.RequestBase64Body
        authentication_ticket = await self._get_authentication_token()

        try:
            log.info(f"Submitting assignment letter request: {request_id}")

            submission_result = await self._send_to_opentext(
                authentication_ticket, body
            )

            if submission_result:
                status = submission_result.get("status")
                assignment_letter_request.SubmissionResult = json.dumps(submission_result)
                assignment_letter_request.SubmissionStatus = status
                await self._update_request(assignment_letter_request)
                self._log_submission_result(status, request_id, submission_result)
                log.info(f"Assignment letter request {request_id} submission: {status}")

            return submission_result

        except Exception as e:
            log.error(
                f"Failed to submit assignment letter request {request_id}: {e}"
            )
            raise

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _send_to_opentext(self, authentication_ticket, xml_base64_body):
        ssl_context = ssl._create_unverified_context()

        payload = json.dumps(
            {"content": {"contentType": "application/xml", "data": xml_base64_body}}
        )

        headers = {
            "OTDSTICKET": authentication_ticket,
            "Content-Type": "application/json",
        }

        endpoint_url = (
            (
                getattr(self.configuration, "opentextAssignmentCreateUrl", None)
                or self.configuration.opentextStatementUrl
            )
            if self.configuration.isLocal
            else self.opentext_endpoint.statement_url
        )

        log.info(f"Assignment letter submission endpoint: {endpoint_url}")

        host, path = Utility.extract_host_and_path(endpoint_url)
        conn = http.client.HTTPSConnection(host, context=ssl_context)

        try:
            conn.request("POST", path, payload, headers)
            response = conn.getresponse()

            if response.status >= 400:
                raise Exception(
                    f"OpenText responded with {response.status}: {response.reason}"
                )

            return json.loads(response.read().decode())
        finally:
            conn.close()

    async def _get_authentication_token(self):
        ssl_context = ssl._create_unverified_context()

        if not self.configuration.isLocal:
            username = self.opentext_endpoint.username
            password = self.opentext_endpoint.password
            endpoint_url = self.opentext_endpoint.auth_url
        else:
            username = self.configuration.opentextUserName
            password = self.configuration.opentextPassword
            endpoint_url = self.configuration.opentextAuthUrl

        log.info(f"Assignment letter auth endpoint: {endpoint_url}")

        payload = json.dumps({"user_name": username, "password": password})
        headers = {"Content-Type": "application/json"}

        host, path = Utility.extract_host_and_path(endpoint_url)
        conn = http.client.HTTPSConnection(host, context=ssl_context)

        try:
            conn.request("POST", path, payload, headers)
            response = conn.getresponse()

            if response.status >= 400:
                raise Exception(
                    f"Auth failed with {response.status}: {response.reason}"
                )

            return json.loads(response.read().decode()).get("ticket")
        finally:
            conn.close()

    def _log_submission_result(self, status, request_id, open_text_response):
        letters = self.assignment_letter_repository.get_by_request_id(request_id)

        if not letters:
            return

        results = open_text_response.get("data", {}).get("result", [])
        result_map = {
            str(item.get("IPR", "")).replace("/", ""): item for item in results
        }

        for letter in letters:
            result = result_map.get(letter.OpenTextIPR)
            if result:
                statuses = result.get("statementProcessingStatus", [])
                letter.PdfGenerationStatus = statuses[0] if statuses else None
                letter.OpenTextTrackerId = result.get("trackerID")
                letter.PdfContent = result.get("content", {}).get("data")
                letter.RequestSubmissionStatus = status

        self.assignment_letter_repository.upsert(letters)

    async def _get_request(self, request_id):
        return self.assignment_letter_request_repository.get_by_id(request_id)

    async def _update_request(self, record):
        self.assignment_letter_request_repository.upsert(record)
