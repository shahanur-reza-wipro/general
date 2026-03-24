import json
import os
import logging
from botocore.exceptions import ClientError
from utilities import Configuration, DbEndpoint, OpenTextEndpoint
from utilities.utility import Utility

logger = logging.getLogger()
logger.setLevel(logging.INFO)


class SecretManager:

    def __init__(self):
        self.configuration = Configuration().get_config()

    def get_secret_by_name(self, secret_name):
        client = Utility.get_boto3_client("secretsmanager", self.configuration)
        try:
            response = client.get_secret_value(SecretId=secret_name)
        except ClientError as e:
            raise e
        else:
            if "SecretString" in response:
                return response["SecretString"]
            return response["SecretBinary"]

    def get_secret_by_arn(self, secret_arn):
        client = Utility.get_boto3_client("secretsmanager", self.configuration)
        try:
            response = client.get_secret_value(SecretId=secret_arn)
        except ClientError as e:
            raise e
        else:
            if "SecretString" in response:
                return response["SecretString"]
            return response["SecretBinary"]

    def get_endpoint(self):
        secret_name = (
            os.getenv("DB_ENDPOINT_SECRET_NAME")
            if self.configuration.isLocal
            else self.configuration.dbEndpointSecretName
        )
        db_endpoint_string = self.get_secret_by_name(secret_name)
        logger.info("db endpoint loaded")
        db_endpoint_data = json.loads(db_endpoint_string)
        db_endpoint = DbEndpoint(**db_endpoint_data)

        db_password_string = self.get_secret_by_arn(db_endpoint.password_secret_arn)
        db_password_detail = json.loads(db_password_string)
        db_endpoint.password = db_password_detail["password"]

        return db_endpoint

    def get_sns_arn(self):
        secret_name = (
            os.getenv("SNS_ARN_SECRET_NAME")
            if self.configuration.isLocal
            else self.configuration.snsArnSecretName
        )
        sns_arn_secret = self.get_secret_by_name(secret_name)
        sns_arn_secret_data = json.loads(sns_arn_secret)
        return sns_arn_secret_data["sns_topic_arn"]

    def get_opentext_endpoint(self):
        secret_name = (
            os.getenv("OPENTEXT_SECRET_NAME")
            if self.configuration.isLocal
            else self.configuration.openTextSecretName
        )
        opentext_string = self.get_secret_by_name(secret_name)
        opentext_data = json.loads(opentext_string)
        opentext_endpoint = OpenTextEndpoint(**opentext_data)
        opentext_password_string = self.get_secret_by_arn(
            opentext_endpoint.password_secret_arn
        )
        # opentext_password_detail = json.loads(opentext_password_string)
        # opentext_endpoint.password = opentext_password_detail["password"]
        opentext_endpoint.password = opentext_password_string["password"]
        return opentext_endpoint