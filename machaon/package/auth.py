import urllib.request
import base64

#
#
#
class basic_auth():
    def __init__(self, password, raw=False):
        if not raw:
            password = base64.b64decode(password).decode("utf-8")
        self.password = password
    
    def build_request(self, rep, url, **kwargs):    
        headers = kwargs.get("headers", {})
        authcode = base64.b64encode("{}:{}".format(rep.username, self.password).encode("utf-8"))
        headers["authorization"] = "Basic {}".format(authcode.decode("ascii"))
        kwargs["headers"] = headers
        req = urllib.request.Request(url=url, **kwargs)
        return req
        