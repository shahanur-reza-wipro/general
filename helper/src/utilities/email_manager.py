import os
import json
from utilities.utility import Utility
from datetime import datetime
from zoneinfo import ZoneInfo


class EmailManager:
    TEMPLATE_JSON_FILE = "email_template.json"

    def _get_email_template(self, template_name, directory=os.path.dirname(__file__)):
        print(f"loading config from {self.TEMPLATE_JSON_FILE}")
        json_file_path = os.path.join(directory, self.TEMPLATE_JSON_FILE)
        print(json_file_path)
        with open(json_file_path, "r") as file:
            data = json.load(file)
            print("json data loaded")

        return data["templates"][template_name]

    def prepare_email(self, template_args, email_template_name):
        email_template = self._get_email_template(email_template_name)
        subject = email_template["subject"]
        body = email_template["body"]
        args = email_template["args"]

        args_list = args.split(",")
        args_dict = {key: template_args.get(key, "") for key in args_list}

        subject, body = self.create_message(
            subject=subject,
            body=body,
            **args_dict,
        )

        return subject, body

    def create_message(self, subject, body, **kwargs):
        subject = subject.format(**kwargs)
        body = body.format(**kwargs)
        return subject, body