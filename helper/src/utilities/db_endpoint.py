class DbEndpoint:

    def __init__(
        self,
        db_endpoint="",
        proxy_endpoint="",
        username="",
        db_name="",
        password_secret_arn="",
        password="",
    ):
        self.db_endpoint = db_endpoint
        self.proxy_endpoint = proxy_endpoint
        self.username = username
        self.db_name = db_name
        self.password_secret_arn = password_secret_arn
        self.password = password

    def to_dict(self):
        return {
            "db_endpoint": self.db_endpoint,
            "proxy_endpoint": self.proxy_endpoint,
            "username": self.username,
            "db_name": self.db_name,
            "password_secret_arn": self.password_secret_arn,
            "password": self.password,
        }