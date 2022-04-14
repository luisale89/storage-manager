from .helpers import JSONResponse

class APIException(Exception, JSONResponse):

    def __init__(self, message, app_result="error", status_code=400, payload=None): #default code 400

        Exception.__init__(self)
        JSONResponse.__init__(self, message, app_result, status_code, payload)


class TokenNotFound(Exception):
    """
    Indicates that a token could not be found in the database
    """
    pass 