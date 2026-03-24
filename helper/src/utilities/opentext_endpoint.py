class OpenTextEndpoint:
    def __init__(self, username="", password="", auth_url="", statement_url="", request_url=""):
        self.auth_url = auth_url
        self.statement_url = statement_url
        self.request_url = request_url
        self.username = username
        self.password = password
    
    def to_dict(self):
        return {
            "username": self.username,
            "password": self.password,
            "auth_url": self.auth_url,
            "statement_url": self.statement_url,
            "request_url": self.request_url
        }