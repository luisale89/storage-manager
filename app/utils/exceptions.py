import logging
from .helpers import JSONResponse

logger = logging.getLogger(__name__)
class APIException(Exception, JSONResponse):

    def __init__(self, message, app_result="error", status_code=400, payload=None): #default code 400
        logger.info(f'APIException rised with msg: {message} \ status_code: {status_code}')
        Exception.__init__(self)
        JSONResponse.__init__(self, message, app_result, status_code, payload)


class TokenNotFound(Exception):
    """
    Indicates that a token could not be found in the database
    """
    pass 