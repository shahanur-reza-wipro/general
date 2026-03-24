# utility.py
import base64
import csv
from io import StringIO
import json
import xml.dom.minidom
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime
import boto3


class Utility:

    @staticmethod
    def convert_to_float(data):
        if data == "":
            return None
        try:
            return float(data)
        except ValueError:
            return data

    @staticmethod
    def convert_to_date(data, date_format="%d/%m/%y"):
        if data is None:
            return None

        if isinstance(data, (date, datetime)):
            return data.date() if isinstance(data, datetime) else data

        data = str(data).strip()
        if data == "":
            return None

        formats = [date_format]
        for supported_format in ["%d/%m/%y", "%Y%m%d"]:
            if supported_format not in formats:
                formats.append(supported_format)

        for supported_format in formats:
            try:
                return datetime.strptime(data, supported_format).date()
            except ValueError:
                continue

        return data

    @staticmethod
    def chunk_data(data, chunk_size=1000):
        for i in range(0, len(data), chunk_size):
            yield data[i : i + chunk_size]

    @staticmethod
    def is_none_or_empty(value):
        if value is None:
            return True
        if isinstance(value, (str, list, dict)):
            return len(value) == 0
        return False

    @staticmethod
    def dict_to_xml(tag, dictionary):
        doc = xml.dom.minidom.Document()
        root = doc.createElement(tag)
        doc.appendChild(root)

        def build_xml_element(parent, key, value):
            if isinstance(value, dict):
                element = doc.createElement(key)
                for k, v in value.items():
                    build_xml_element(element, k, v)
                parent.appendChild(element)
            elif isinstance(value, list):
                for item in value:
                    build_xml_element(parent, key, item)
            else:
                element = doc.createElement(key)
                element.appendChild(doc.createTextNode(str(value)))
                parent.appendChild(element)

        for key, val in dictionary.items():
            build_xml_element(root, key, val)

        return doc.toprettyxml(indent="  ")

    @staticmethod
    def serialize_to_xml(data, data_class_name=None):
        data_dict = asdict(data)
        dc = data.__class__.__name__ if data_class_name is None else data_class_name
        return Utility.dict_to_xml(dc, data_dict)

    @staticmethod
    def encode_to_base64(data: str):
        base64_data = base64.b64encode(data.encode("utf-8")).decode("utf-8")
        return base64_data

    @staticmethod
    def decode_to_base64(encoded_str: str):
        decoded_bytes = base64.b64decode(encoded_str)
        return decoded_bytes.decode("utf-8")

    @staticmethod
    def load_from_json(
        object_type, file_name, directory=os.path.dirname(__file__)
    ):
        print(f"loading config from {file_name}")
        json_file_path = os.path.join(directory, file_name)
        print(json_file_path)
        with open(json_file_path, "r") as file:
            data = json.load(file)
            print("json data loaded")
        return object_type(**data)

    @staticmethod
    def load_from_json_as_dictionary(
        file_name, directory=os.path.dirname(__file__)
    ):
        print(f"loading config from {file_name}")
        json_file_path = os.path.join(directory, file_name)
        print(json_file_path)
        with open(json_file_path, "r") as file:
            data = json.load(file)
            print("json data loaded")
        return data

    @staticmethod
    def extract_host_and_path(url):
        """Helper function to extract host and path from a URL"""
        from urllib.parse import urlparse

        parsed_url = urlparse(url)
        host = parsed_url.netloc
        path = parsed_url.path
        if parsed_url.query:
            path += "?" + parsed_url.query
        return host, path

    @staticmethod
    def get_file_content_type(file_name):
        if file_name.startswith("A"):
            return "Debtor"
        if file_name.startswith("B"):
            return "Transaction"
        return ""

    @staticmethod
    def generate_pdf(base64PDFContent, file_name):
        with open(file_name, "wb") as pdf_file:
            pdf_file.write(base64.b64decode(base64PDFContent))

    @staticmethod
    def get_boto3_client(
        service_name,
        configuration,
        aws_access_key_id=None,
        aws_secret_access_key=None,
        aws_session_token=None,
    ):
        if configuration.isLocal:
            return boto3.client(
                service_name,
                region_name=configuration.region,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key,
                aws_session_token=aws_session_token,
            )
        else:
            return boto3.client(service_name, region_name=configuration.region)

    @staticmethod
    def generate_csv(records: list, column_names: list):
        try:
            iter(records)
        except TypeError:
            raise ValueError("The argument records must be an iterable.")

        csv_object = StringIO()
        writer = csv.DictWriter(csv_object, fieldnames=column_names)
        writer.writeheader()

        for record in records:
            if not isinstance(record, dict):
                raise ValueError("Each Item in records must be a dictionary.")
            writer.writerow(record)

        csv_object.seek(0)
        return csv_object

    @staticmethod
    def encode_to_base64_with_padding(data):
        # convert xml string to base_64
        base64_data = Utility.encode_to_base64(data)
        # add padding
        while len(base64_data) % 4 != 0:
            base64_data += "="
        return base64_data

    @staticmethod
    def json_serializer(obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        raise TypeError(f"Type {type(obj)} not serializable")