from .helpers import JSONResponse

class APIException(Exception, JSONResponse):

    def __init__(self, message, app_result="error", status_code=400, payload=None): #default code 400
        Exception.__init__(self)
        JSONResponse.__init__(self, message, app_result, status_code, payload)

    @classmethod
    def from_error(cls, error):
        '''creates a APIException instance from an error message dict'''
        
        status_code = error.get('status_code', 400) #400 is the default status code
        msg = error.get('msg', '-no msg-')
        payload = error.get('payload', '-no-data-')

        return cls(message=msg, payload=payload, status_code=status_code)