from datetime import datetime
import http.client
import json
import ssl
import logging

from data_access_layer.models.statement import Statement
from repositories import StatementRepository, StatementRequestRepository
from services.statement_submit_notification_service import StatementSubmitNotificationService
from utilities import Utility, Configuration, SecretManager

log = logging.getLogger()


class StatementRequestSubmissionService:

    def __init__(self):
        self.statement_repository = StatementRepository()
        self.configuration = Configuration().get_config()
        self.opentext_endpoint = SecretManager().get_opentext_endpoint() if not self.configuration.isLocal else None
        self.statement_request_repository = StatementRequestRepository()
        self.statement_submit_notification_service = StatementSubmitNotificationService()

    async def submit_to_opentext(self, statement_request):
        if not statement_request:
            return

        request = json.loads(statement_request)
        request_id = request["request_id"]

        statement_request = await self.get_statement_request(request_id)

        if statement_request:
            body = statement_request.StatementBase64RequestBody

            authentication_ticket = await self.get_authentication_token()

            try:
                print(f"Submitting statement generation for: {request_id}")

                submission_result = await self.send_for_statement_generation(
                    authentication_ticket,
                    body
                )

                if submission_result:
                    submission_status = submission_result["status"]

                    self.log_statement_submission_result(
                        submission_status,
                        statement_request_id=request_id,
                        open_text_response=submission_result
                    )

                    statement_request.SubmissionResult = json.dumps(submission_result)
                    statement_request.SubmissionStatus = submission_status

                    await self.update_submission_result(statement_request)

                    await self.statement_submit_notification_service.notify()

                    print(
                        f"Statement Request: {request_id} statement generation was: {submission_status}"
                    )

            except Exception as e:
                print(
                    f"Failed to process and send for statement generation; Statement Request: {request_id}; Error: {e}"
                )
                raise e

        return submission_result

    async def send_for_statement_generation(self, authentication_ticket, xml_base64_statement):

        ssl_context = ssl._create_unverified_context()

        payload = json.dumps({
            "content": {
                "contentType": "application/xml",
                "data": xml_base64_statement
            }
        })

        headers = {
            "OTDSTICKET": f"{authentication_ticket}",
            "Content-Type": "application/json"
        }

        endpoint_url = (
            self.configuration.opentextStatementUrl
            if self.configuration.isLocal
            else self.opentext_endpoint.statement_url
        )

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

    async def get_authentication_token(self):

        ssl_context = ssl._create_unverified_context()

        if not self.configuration.isLocal:
            username = self.opentext_endpoint.username
            password = self.opentext_endpoint.password
            endpoint_url = self.opentext_endpoint.auth_url
        else:
            username = self.configuration.opentextUserName
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
                raise Exception(
                    f"Request failed with status {response.status}: {response.reason}"
                )

            response_data = response.read().decode()
            response_json = json.loads(response_data)

            return response_json.get("ticket")

        finally:
            conn.close()

    def log_statement_submission_result(
        self,
        submission_status,
        statement_request_id=None,
        open_text_response=None
    ):

        statements = []
        debtor_submission_results = open_text_response["data"]["result"]

        debtor_map = {
            str(item["IPR"]).replace("/", ""): item
            for item in debtor_submission_results
        }

        statements = self.statement_repository.get_statements_by_request_id(
            statement_request_id
        )

        if statements:
            for statement in statements:
                debtor_submission_result = debtor_map.get(statement.OpenTextIPR)

                if debtor_submission_result:
                    pdf_generation_status = debtor_submission_result[
                        "statementProcessingStatus"
                    ][0]

                    opentext_tracker_id = debtor_submission_result["trackerID"]

                    pdf_content = debtor_submission_result["content"]["data"]

                    statement.PdfGenerationStatus = pdf_generation_status
                    statement.OpenTextTrackerId = opentext_tracker_id
                    statement.PdfContent = pdf_content
                    statement.RequestSubmissionStatus = submission_status

            self.statement_repository.upsert(statements)

    async def get_statement_request(self, request_id):
        statement_request = self.statement_request_repository.get_by_id(request_id)
        return statement_request

    async def update_submission_result(self, statement_request):
        self.statement_request_repository.upsert(statement_request)