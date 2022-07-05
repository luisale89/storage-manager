import logging
from datetime import datetime, timedelta
from dateutil.parser import parse, ParserError
from datetime import timezone
from random import sample
import string
from typing import Union
from flask import jsonify
from app.utils.func_decorators import app_logger

logger = logging.getLogger(__name__)


@app_logger(logger)
def _epoch_utc_to_datetime(epoch_utc):
    """
    Helper function for converting epoch timestamps into
    python datetime objects, in UTC
    """
    response = datetime.utcfromtimestamp(epoch_utc)
    return response


@app_logger(logger)
def random_password(length: int = 16) -> str:
    """
    function creates a random password, default length is 16 characters. pass in required length as an integer parameter
    """
    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    nums = string.digits
    symbols = string.punctuation

    all_values = lower + upper + nums + symbols
    password = "".join(sample(all_values, length))

    return password


@app_logger(logger)
def normalize_datetime(raw_date: datetime) -> Union[datetime, None]:
    """
    Helper function for normalize datetime and store them in the database.
    The normalized datetime is naive, and utc based
    """
    try:
        dt = parse(raw_date)
        if dt.tzinfo is not None:  # if a timezone info has been passed in
            date = dt.astimezone(timezone.utc).replace(tzinfo=None)  # store the date as naive datetime.
        else:
            date = dt
    except ParserError:
        date = None

    return date


@app_logger(logger)
def datetime_formatter(target_dt: datetime) -> str:
    """
    returns a string that represents datetime stored in database, in UTC timezone

    datetime representation format: %Y-%m-%dT%H:%M:%S%z

    * Parameters:
    <datetime> a valid datetime instance
    """
    return target_dt.strftime("%Y-%m-%dT%H:%M:%SZ")


@app_logger(logger)
def normalize_string(target_string: str, spaces: bool = False) -> str:
    """
    Normalize a characters string.
    Args:
        target_string (str): cadena de caracteres a normalizar.
        spaces (bool, optional): Indica si la cadena de caracteres incluye o no espacios. 
        Defaults to False.
    Returns:
        str: Candena de caracteres normalizada.
    """
    if not spaces:
        response = target_string.replace(" ", "")
    else:
        response = target_string.strip()

    return response


class JSONResponse:
    """
    Genera mensaje de respuesta a las solicitudes JSON. los parametros son:

    - message: Mesanje a mostrar al usuario.
    - app_result = "success", "error"
    - status_code = http status code
    - payload = dict con cualquier informacion que se necesite enviar al usuario.

    methods:

    - serialize() -> return dict
    - to_json() -> http JSON response

    """

    def __init__(self, message="ok", app_result="success", status_code=200, payload=None):
        self.app_result = app_result
        self.status_code = status_code
        self.data = payload
        self.message = message

    def __repr__(self) -> str:
        return f'JSONResponse(status_code={self.status_code})'

    def serialize(self):
        rv = {
            "result": self.app_result,
            "data": dict(self.data or ()),
            "message": self.message
        }
        return rv

    @app_logger(logger)
    def to_json(self):
        return jsonify(self.serialize()), self.status_code


class ErrorMessages:

    def __init__(self, parameters=None, custom_msg=None):
        self.custom_msg = custom_msg
        if parameters is None:
            self.parameters = []
        elif not isinstance(parameters, list):
            self.parameters = [parameters]
        else:
            self.parameters = parameters

    def __repr__(self) -> str:
        return f'ErrorMessages(parameters={self.parameters})'

    def get_response(self, message, status_code):
        msg = self.custom_msg if self.custom_msg is not None else message
        return {'msg': msg, 'payload': {'error': self.parameters}, 'status_code': status_code}

    @property
    def bad_request(self):
        """status_code = 400"""
        return self.get_response(message='bad request, check data inputs and try again', status_code=400)

    @property
    def unauthorized(self):
        """status_code = 401"""
        return self.get_response(message='user not authorized to get the request', status_code=401)

    @property
    def user_not_active(self):
        """status_code = 402"""
        return self.get_response(message='user is not active or has been disabled', status_code=402)

    @property
    def wrong_password(self):
        """status_code = 403"""
        return self.get_response(message='wrog password, try again', status_code=403)

    @property
    def notFound(self):
        """status_code = 404"""
        return self.get_response(message='parameter not found in the database', status_code=404)

    @property
    def notAcceptable(self):
        """status_code = 406"""
        return self.get_response(message='no valid inputs were found in request body', status_code=406)

    @property
    def conflict(self):
        """status_code = 409"""
        return self.get_response(message='parameter already exists in the database', status_code=409)

    @property
    def service_unavailable(self):
        """status_code = 503"""
        return self.get_response(message='requested service unavailable', status_code=503)


class DefaultContent:

    def __init__(self):
        self.item_image = "https://server.com/default-item.png"
        self.user_image = "https://server.com/default-user.png"
        self.company_image = "https://server.com/default-company.png"
        self.currency = {"name": "US Dollar", "code": "USD", "rate-usd": 1.0}


class QueryParams:

    def __init__(self, params) -> None:
        self.params_flat = params.to_dict()
        self.params_non_flat = params.to_dict(flat=False)

    def __repr__(self) -> str:
        return f'QueryParams(parameters={self.params_non_flat})'

    @staticmethod
    @app_logger(logger)
    def normalize_parameter(value):
        """
        Given a non-flattened query parameter value,
        and if the value is a list only containing 1 item,
        then the value is flattened.

        param value: a value from a query parameter
        return: a normalized query parameter value
        """
        return value if len(value) > 1 else value[0]

    @app_logger(logger)
    def normalize_query(self) -> dict:
        """
        Converts query parameters from only containing one value for each parameter,
        to include parameters with multiple values as lists.

        :return: a dict of normalized query parameters
        """
        return {k: self.normalize_parameter(v) for k, v in self.params_non_flat.items()}

    @app_logger(logger)
    def get_all_values(self, key: str) -> Union[list, None]:
        """return all values for specified key.
        return None if key is not found in the parameters
        """
        return self.params_non_flat.get(key, None)

    @app_logger(logger)
    def get_first_value(self, key: str) -> str:
        """return first value in the list of specified key.
        return empty string if key is not found in the parameters
        """
        return self.params_flat.get(key, '')

    @app_logger(logger)
    def get_all_integers(self, key: str) -> Union[list, None]:
        """returns a list of integers created from a list of values in the request. 
        if the conversion fails, the value is ignored
        > parameters: (key: str)
        > returns: values: [list || None]

        if no items was successfully converted to integer value, 
        an empty list is returned.
        """
        values = self.get_all_values(key)
        if values:
            return [int(v) for v in values if str_to_int(v)]
        return None


def str_to_int(value: str) -> Union[int, None]:
    """Convierte una cadena de caracteres a su equivalente entero. Si la conversion no es vaida devuelve None"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return None
