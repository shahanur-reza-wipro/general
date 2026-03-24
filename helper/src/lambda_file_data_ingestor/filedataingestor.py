import json
import boto3
import urllib.parse
from services import DebtorService, TransactionService, FileReceiptService, FileProcessedService


def starts_with(file_name, char):
    return file_name.startswith(char)


def lambda_handler(event, context):
    # Get the S3 bucket and object key from the event
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']

    # decode s3 object key
    key = urllib.parse.unquote_plus(key)

    s3_client = boto3.client('s3')
    response = s3_client.get_object(Bucket=bucket, Key=key)

    file_content = response['Body'].read().decode('utf-8', errors='replace')
    lines = file_content.splitlines()

    file_receive_service = FileReceiptService()
    file_receive_service.notify(key)

    result = f'{key} was not processed'

    if starts_with(key, 'A'):
        debtor_service = DebtorService()
        result = debtor_service.process_debtors(lines, key)

    if starts_with(key, 'B'):
        transaction_service = TransactionService()
        result = transaction_service.process_transactions(lines, key)

    # Return a success message
    return {
        'statusCode': 200,
        'body': json.dumps(f'file processing result: {result}')
    }