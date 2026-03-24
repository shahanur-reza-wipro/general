# main.py
import asyncio
import datetime
import json
import time
from io import BytesIO

from data_access_layer.models.debtor import Debtor
from data_access_layer.models.run_control import RunControl
from data_access_layer.models.transaction import Transaction
import os
from data_access_layer.database import Database
from services.transaction_service import TransactionService
from services.debtor_service import DebtorService
from services.file_receipt_service import FileReceiptService
from services.file_validation_service import FileValidationService
from utilities.coniguration import Configuration
from utilities.utility import Utility

# LocalStack Configuration
os.environ['AWS_ENDPOINT_URL'] = 'http://localhost:4566'
os.environ['AWS_ACCESS_KEY_ID'] = 'test'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'test'
os.environ['AWS_REGION'] = 'eu-west-2'
os.environ['ENV_ID'] = 'd'
os.environ['ENV_INSTANCE_ID'] = '01'

debtor_file_path = os.path.join(
    os.path.dirname(__file__),
    "../extract_files\\dss2\\ADISTMOUT3202505202803017.txt",
)  # ADISTMOUT3202505202803029

transaction_file_path = os.path.join(
    os.path.dirname(__file__),
    "../extract_files\\dss2\\BDISTMOUT320250325164017.txt",
)  # BDISTMOUT3202505202803007


# debtor_file_path = os.path.join(
#     os.path.dirname(__file__), "../ADISTMOUT3202405020803000.txt"
# )
# transaction_file_path = os.path.join(
#     os.path.dirname(__file__), "../BDISTMOUT3202405020803000.txt"
# )


def process_debtors(file, file_name):
    debtor_service = DebtorService()
    debtors = debtor_service.process_debtors(file, file_name)


def process_transactions(file, file_name):
    transaction_service = TransactionService()
    transactions = transaction_service.process_transactions(file, file_name)


def insert_orchestration(isDebtor):
    if isDebtor:
        file_path = debtor_file_path
    else:
        file_path = transaction_file_path

    with open(file_path, "r") as file:
        file_name = os.path.basename(file.name)

        # Mimic lambda flow: file receipt notification first, then route by file type
        file_receipt_service = FileReceiptService()
        file_receipt_service.notify(file_name)

        if starts_with(file_name, "A"):
            process_debtors(file, file_name)
        elif starts_with(file_name, "B"):
            process_transactions(file, file_name)


def ingest_via_filedataingestor_lambda(file_path):
    import lambda_file_data_ingestor.filedataingestor as filedataingestor_lambda

    file_name = os.path.basename(file_path)

    class _LocalMockS3Client:
        def __init__(self, file_mapping):
            self.file_mapping = file_mapping

        def get_object(self, Bucket, Key):
            local_path = self.file_mapping.get(Key)
            if not local_path:
                raise FileNotFoundError(f"No local file mapped for S3 key: {Key}")
            with open(local_path, "r", encoding="utf-8") as f:
                content = f.read().encode("utf-8")
            return {"Body": BytesIO(content)}

    file_mapping = {file_name: file_path}
    original_boto3_client = filedataingestor_lambda.boto3.client

    def _mock_boto3_client(service_name, *args, **kwargs):
        if service_name == "s3":
            return _LocalMockS3Client(file_mapping)
        return original_boto3_client(service_name, *args, **kwargs)

    try:
        filedataingestor_lambda.boto3.client = _mock_boto3_client
        lambda_event = {
            "Records": [
                {
                    "s3": {
                        "bucket": {"name": "local-bucket"},
                        "object": {"key": file_name},
                    }
                }
            ]
        }
        return filedataingestor_lambda.lambda_handler(lambda_event, None)
    finally:
        filedataingestor_lambda.boto3.client = original_boto3_client


def validate_file(isDebtor):
    if isDebtor:
        file_path = debtor_file_path
    else:
        file_path = transaction_file_path

    with open(file_path, "r") as file:
        file_name = os.path.basename(file.name)
        file_service = FileValidationService()
        if starts_with(file_name, "A"):
            file_service.validate_debtor_file(file, file_name)
        else:
            file_service.validate_transaction_file(file, file_name)


def starts_with(file_name, char):
    return file_name.startswith(char)


start_time = time.time()

print(os.getenv("AWS_"))

config = Configuration()
config_data = config.get_config()
print(f"env: {config_data.env}")
print(f"dbEndpointSecretName: {config_data.dbEndpointSecretName}")

# 0: Reset Database
db = Database()
db.reset_database()
db.create_tables()

# 1: File Receipt (disabled - requires AWS SNS)
# fileReceiptService = FileReceiptService()
# fileReceiptService.notify("ABC12933EE.dat")
# fileReceiptService.notify("BDISTMOUT320250325164002.txt")

# 2: Validate File (disabled - requires AWS SNS)
# validate_file(True)
# validate_file(False)

# 3: Data Ingestion
print("\n========== INGESTING DATA ==========")
debtor_ingestion_result = ingest_via_filedataingestor_lambda(debtor_file_path)
transaction_ingestion_result = ingest_via_filedataingestor_lambda(transaction_file_path)

print(f"Debtor ingestion result: {debtor_ingestion_result}")
print(f"Transaction ingestion result: {transaction_ingestion_result}")

print("\n[OK] Data ingestion completed successfully!")
print(f"Execution time: {time.time() - start_time:.2f}s")

# 4: Process Assignment Letter Validation Queue (queued by FileProcessedService)
print("\n========== TESTING ASSIGNMENT LETTER GENERATION ==========")
from utilities.sqs_helper import SQSHelper
from lambda_assignment_letter_validator.assignmentlettervalidator import lambda_handler as validator_lambda_handler

# Process orchestrator queue messages
orchestrator_queue_name = config_data.assignmentLetterOrchestratorQueueName
orchestrator_sqs_helper = SQSHelper(orchestrator_queue_name)

orchestrator_messages = []
while True:
    messages = orchestrator_sqs_helper.receive_messages(max_messages=10)
    if not messages:
        break
    orchestrator_messages.extend(messages)

print(f"[OK] Received {len(orchestrator_messages)} orchestrator queue messages")

# Invoke validator lambda handler for each message
messages_processed = 0
for message in orchestrator_messages:
    try:
        lambda_event = {
            'Records': [
                {
                    'body': message['Body']
                }
            ]
        }
        result = validator_lambda_handler(lambda_event, None)
        print(f"[OK] Validator lambda processed message. Result: {result}")
        orchestrator_sqs_helper.delete_message(message['ReceiptHandle'])
        messages_processed += 1
    except Exception as e:
        print(f"[ERROR] Failed to process orchestrator message: {str(e)}")
        orchestrator_sqs_helper.delete_message(message['ReceiptHandle'])

print(f"[OK] Processed {messages_processed} orchestrator messages with validator lambda")

# Check assignment requests queue
requests_queue_name = config_data.assignmentLetterRequestsQueueName
request_sqs_helper = SQSHelper(requests_queue_name)
request_messages = request_sqs_helper.receive_messages(max_messages=10)
print(f"[OK] Assignment letter requests queue has {len(request_messages)} message(s)")

for msg in request_messages:
    print(f"    Request body: {msg['Body']}")

# 5: Submit Assignment Letter Requests
print("\n========== TESTING ASSIGNMENT LETTER REQUEST SUBMITTER ==========")
from lambda_assignment_letter_request_submitter.assignmentletterrequestsubmitter import lambda_handler as request_submitter_lambda_handler

if request_messages:
    submitter_processed = 0
    for msg in request_messages:
        try:
            submitter_event = {
                "Records": [
                    {
                        "body": msg["Body"]
                    }
                ]
            }
            submitter_result = request_submitter_lambda_handler(submitter_event, None)
            print(f"[OK] Request submitter lambda processed message. Result: {submitter_result}")
            request_sqs_helper.delete_message(msg["ReceiptHandle"])
            submitter_processed += 1
        except Exception as e:
            print(f"[ERROR] Failed to process assignment request message: {str(e)}")

    print(f"[OK] Processed {submitter_processed} assignment request submitter message(s)")
else:
    print("[INFO] No assignment request messages found to submit")

# 6: Process Dunning Letter Validation Queue (queued by FileProcessedService)
print("\n========== TESTING DUNNING LETTER GENERATION ==========")
from lambda_dunning_letter_orchestrator.dunningletterorchestrator import lambda_handler as dunning_validator_lambda_handler

# Process dunning orchestrator queue messages
dunning_orchestrator_queue_name = config_data.dunningLetterOrchestratorQueueName
dunning_orchestrator_sqs_helper = SQSHelper(dunning_orchestrator_queue_name)

dunning_orchestrator_messages = []
while True:
    messages = dunning_orchestrator_sqs_helper.receive_messages(max_messages=10)
    if not messages:
        break
    dunning_orchestrator_messages.extend(messages)

print(f"[OK] Received {len(dunning_orchestrator_messages)} dunning orchestrator queue messages")

# Invoke dunning validator lambda handler for each message
dunning_messages_processed = 0
for message in dunning_orchestrator_messages:
    try:
        lambda_event = {
            'Records': [
                {
                    'body': message['Body']
                }
            ]
        }
        result = dunning_validator_lambda_handler(lambda_event, None)
        print(f"[OK] Dunning validator lambda processed message. Result: {result}")
        dunning_orchestrator_sqs_helper.delete_message(message['ReceiptHandle'])
        dunning_messages_processed += 1
    except Exception as e:
        print(f"[ERROR] Failed to process dunning orchestrator message: {str(e)}")
        dunning_orchestrator_sqs_helper.delete_message(message['ReceiptHandle'])

print(f"[OK] Processed {dunning_messages_processed} dunning orchestrator messages with validator lambda")

# Check dunning requests queue
dunning_requests_queue_name = config_data.dunningLetterRequestsQueueName
dunning_request_sqs_helper = SQSHelper(dunning_requests_queue_name)
dunning_request_messages = dunning_request_sqs_helper.receive_messages(max_messages=10)
print(f"[OK] Dunning letter requests queue has {len(dunning_request_messages)} message(s)")

for msg in dunning_request_messages:
    print(f"    Dunning request body: {msg['Body']}")

# 7: Submit Dunning Letter Requests
print("\n========== TESTING DUNNING LETTER REQUEST SUBMITTER ==========")
from lambda_dunning_letter_request_submitter.dunningletterrequestsubmitter import lambda_handler as dunning_request_submitter_lambda_handler

if dunning_request_messages:
    dunning_submitter_processed = 0
    for msg in dunning_request_messages:
        try:
            dunning_submitter_event = {
                "Records": [
                    {
                        "body": msg["Body"]
                    }
                ]
            }
            dunning_submitter_result = dunning_request_submitter_lambda_handler(dunning_submitter_event, None)
            print(f"[OK] Dunning request submitter lambda processed message. Result: {dunning_submitter_result}")
            dunning_request_sqs_helper.delete_message(msg["ReceiptHandle"])
            dunning_submitter_processed += 1
        except Exception as e:
            print(f"[ERROR] Failed to process dunning request message: {str(e)}")

    print(f"[OK] Processed {dunning_submitter_processed} dunning request submitter message(s)")
else:
    print("[INFO] No dunning request messages found to submit")

# # # # 4: Queue Debtors for Statement Generation
# statement_orchestration_service = StatementOrchestrationService()
# list_of_queued_iprs, submission_id = statement_orchestration_service.queue_to_validate_statement_generation()

# statement_requests_for_queue = []

# statement_validation_service = StatementValidationService()
# for queued_iprs in list_of_queued_iprs:
#     validation_result = statement_validation_service.validate(queued_iprs)
#     if validation_result:
#         statement_requests, request_id = validation_result
#         request = {}
#         request["request_id"] = request_id
#         #request["body"] = statement_requests
#         statement_requests_for_queue.append(request)

# # # # 5: Submit Request for Statement Generation
# statement_request_submission_service = StatementRequestSubmissionService()
# submission_results = []
# for request in statement_requests_for_queue:
#     statement_request = {
#         "request_id": str(request_id)
#     }
#     result = asyncio.run(statement_request_submission_service.submit_to_opentext(json.dumps(statement_request)))
#     submission_results.append(result)

# # # for submission_result in submission_results:
# # #     data = submission_result['data']['result']
# # #     for ipr in debtor_submission_report['IPR']
# # #         pdf_content = debtor_submission_report['content']['data']
# # #         Utility.generate_pdf(pdf_content,f"{str(ipr[0])}.pdf")

# # # pdf_count = StatementRequestRepository().get_total_expected_statement_count(datetime.date.today())

# extractFilesProcessingStatusReportService = FilesProcessingStatusReportService()
# extractFilesProcessingStatusReportService.send_report(str(submission_id))
# report = extractFilesProcessingStatusReportService.get_report()
# with open("statement_processing_report.csv", "w", newline="") as file:
#     file.write(report.getvalue())

# print(f"total pdf: {pdf_count}")
# configuration = Configuration().get_config()
# filesProcessingStatusReportSchedulerService = FilesProcessingStatusReportSchedulerService(configuration.fileProcessedReportGeneratorLambdaDetailsSecretName)
# filesProcessingStatusReportSchedulerService.delete_schedule_rule()
# end_time = time.time()
# execution_time = end_time - start_time
# print(f"execution time: {execution_time}")