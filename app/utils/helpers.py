import os
import re
import logging
import unicodedata
import string
from datetime import datetime, timezone
from dateutil.parser import parse, ParserError
from random import sample
from typing import Union
from flask import jsonify
from app.utils.func_decorators import app_logger
from itsdangerous import BadSignature, Signer

logger = logging.getLogger(__name__)

class DateTimeHelpers:
    """Datetime instance with helpers methods"""
    def __init__(self, datetime:datetime = None) -> None:
        self.datetime = datetime

    def __repr__(self) -> str:
        return f"DateTimeHelpers({self.datetime})"

    def __bool__(self) -> bool:
        return True if isinstance(self.datetime, datetime) else False
    

    def datetime_formatter(self) -> str:
        """
        returns a string that represents datetime stored in database, in UTC timezone

        datetime representation format: %Y-%m-%dT%H:%M:%S%z

        * Parameters:
        <datetime> a valid datetime instance
        """
        return self.datetime.strftime("%Y-%m-%dT%H:%M:%SZ")


    def normalize_datetime(self) -> Union[datetime, None]:
        """
        Helper function for normalize datetime and store them in the database.
        The normalized datetime is naive, and utc based
        """
        try:
            dt = parse(self.datetime)
            if dt.tzinfo is not None:  # if a timezone info has been passed in
                date = dt.astimezone(timezone.utc).replace(tzinfo=None)  # store the date as naive datetime.
            else:
                date = dt
        except ParserError:
            date = None

        return date


    @staticmethod
    def _epoch_utc_to_datetime(epoch_utc):
        """
        Helper function for converting epoch timestamps into
        python datetime objects, in UTC
        """
        response = datetime.utcfromtimestamp(epoch_utc)
        return response


class QueryParams:
    """class that represents the query paramteres in request."""

    def __init__(self, params) -> None:
        self.params_flat = params.to_dict()
        self.params_non_flat = params.to_dict(flat=False)
        self.warnings = []

    def __repr__(self) -> str:
        return f'QueryParams(parameters={self.params_non_flat})'


    @staticmethod
    @app_logger(logger)
    def _normalize_parameter(value:list):
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
        return {k: self._normalize_parameter(v) for k, v in self.params_non_flat.items()}


    @app_logger(logger)
    def get_all_values(self, key: str) -> Union[list, None]:
        """return all values for specified key.
        return None if key is not found in the parameters
        """
        return self.params_non_flat.get(key, None)


    @app_logger(logger)
    def get_first_value(self, key: str, as_integer:bool = False) -> Union[str, int, None]:
        """return first value in the list of specified key.
        return None if key is not found in the parameters
        """
        value = self.params_flat.get(key, None)
        if not value:
            self.warnings.append({key: f"{key} not found in query parameters"})
            return value

        if as_integer:
            int_value = StringHelpers.to_int(value)
            if not int_value:
                self.warnings.append({key: f"{value} can't be converted to 'int', is not a numeric string"})
            return int_value
        
        return value


    @app_logger(logger)
    def get_all_integers(self, key: str) -> Union[list, None]:
        """returns a list of integers created from a list of values in the request. 
        if the conversion fails, the value is warnings
        > parameters: (key: str)
        > returns: values: [list || None]

        if no items was successfully converted to integer value, 
        an empty list is returned.
        """
        values = self.get_all_values(key)
        if not values:
            self.warnings.append({key: f"{key} not found in query parameters"})
            return None

        for v in values:
            if not isinstance(v, int):
                self.warnings.append({key: f"expecting 'int' value for [{key}] parameter, [{v}] was received"})

        return [int(v) for v in values if StringHelpers.to_int(v)]


    @app_logger(logger)
    def get_pagination_params(self) -> tuple:
        """
        function to get pagination parameters from request
        default values are given if no parameter is in request.

        Return Tuple -> (page, limit)
        """
        page = StringHelpers.to_int(self.params_flat.get("page", None))
        limit = StringHelpers.to_int(self.params_flat.get("limit", None))

        if not page:
            self.warnings.append({"page": "pagination parameter [page] not found as [int] in query string"})
            page = 1 #default page value
        if not limit:
            self.warnings.append({"limit": "pagination parameter [limit] not found as [int] in query string"})
            limit = 20 #default limit value

        return page, limit


    @staticmethod
    def get_pagination_form(pag_instance) -> dict:
        """
        Receive a pagination instance from flasksqlalchemy, 
        returns a dict with pagination data in a dict, set to return to the user.
        """
        return {
            "pagination": {
                "pages": pag_instance.pages,
                "has_next": pag_instance.has_next,
                "has_prev": pag_instance.has_prev,
                "current_page": pag_instance.page,
                "total_items": pag_instance.total
            }
        }


    def get_warings(self) -> dict:
        resp = {}
        for w in self.warnings:
            resp.update(w) if isinstance(w, dict) else resp.update({w: "error"})
        return {"query_params_warnings": resp}


class StringHelpers:
    """String Helpers methods"""

    def __init__(self, string:str=None) -> None:
        self._string =  string if isinstance(string, str) else ''

    def __repr__(self) -> str:
        return f"StringHelpers(string:{self.string})"

    def __bool__(self) -> bool:
        return True if self.string else False

    @property
    def string(self) -> str:
        return self._string
    
    @string.setter
    def string(self, new_val:str):
        self._string = new_val if isinstance(new_val, str) else ''

    @property
    def value(self) -> str:
        """returns string without blank spaces at the begining and the end"""
        return self.string.strip()

    @property
    def email_normalized(self) -> str:
        return self.value.lower()

    @property
    def no_accents(self) -> str:
        """returns a string without accented characters
            -not receiving bytes as a string parameter-
        """ 
        nfkd_form = unicodedata.normalize('NFKD', self.value)
        return u"".join([c for c in nfkd_form if not unicodedata.combining(c)])
    

    @staticmethod
    def to_int(tar_string:str) -> int:
        """Convierte una cadena de caracteres a su equivalente entero.
        Si la conversion no es válida, devuelve 0
        """
        if not isinstance(tar_string, str):
            return 0

        try:
            return int(tar_string)
        except Exception:
            return 0


    def normalize(self, spaces: bool = False) -> str:
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
            response = self.value.replace(" ", "")
        else:
            response = self.value

        return response


    def is_valid_string(self, max_length: int = None) -> tuple:
        """
        function validates if a string is valid to be stored in the database.
        Args:
            string (str): string to validate.
            max_length (int): max length of the string.
            empty (bool): True if the string could be empty.
        Returns:
            (invalid:bool, str:error message)
        """
        if not self.value:
            return False, "empty string is invalid"

        if isinstance(max_length, int):
            if len(self.value) > max_length:
                return False, f"Input string is too long, {max_length} characters max."

        return True, "string validated"


    def is_valid_email(self) -> tuple:
        """
        Validates if a string has a valid email format
        Args:
            email (str): email to validate
        Returns tuple:
            (valid:bool, str:error message)
                valid=True if the email is valid
                valid=False if the email is invalid
        """
        if len(self.value) > 320:
            return False, "invalid email length, max is 320 chars"

        # Regular expression that checks a valid email
        ereg = '^[\w]+[\._]?[\w]+[@]\w+[.]\w{2,3}$'
        # ereg = '\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

        if not re.search(ereg, self.value):
            return False, f"invalid email format"

        return True, "valid email format"


    def is_valid_pw(self) -> tuple:
        """
        Check if a password meets the minimum security parameters
        defined for this application.
        Args:
            password (str): password to validate.
        Returns tuple:
            (invalid:bool, str:error message)
        """
        # Regular expression that checks a secure password
        preg = '^.*(?=.{8,})(?=.*\d)(?=.*[a-z])(?=.*[A-Z]).*$'

        if not re.search(preg, self.value):
            return False, "password is invalid"

        return True, "password validated"

    @staticmethod
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


class Validations:
    def __init__(self):
        pass

    def __repr__(self) -> str:
        f"Validations()"

    @staticmethod
    def validate_inputs(inputs:dict) -> dict:
        """
        function to validate that there are no errors in the "inputs" dictionary
        Args:
            inputs (dict): inputs to validate following the format:
                {key: ('error':bool, 'msg':error message)}

            where key is the `key` of the field that is validating. example: email, password, etc.
            the output message will be the sum of all the individual messages separated by a |

        Returns dict:
            {key: error message}
        """
        invalids = {}

        for key, value in inputs.items():
            valid, msg = value
            if not valid:
                invalids.update({key: msg})

        return invalids


class IntegerHelpers:
    def __init__(self, integer=None):
        self._integer = integer if isinstance(integer, int) else 0

    def __repr__(self) -> str:
        return f"IntegerHelpers(integer={self.integer})"

    def __bool__(self) -> bool:
        return True if self.integer else False

    @property
    def integer(self):
        return self._integer
    
    @integer.setter
    def integer(self, new_val):
        self._integer = new_val if isinstance(new_val, int) else 0

    @property
    def value(self):
        return self.integer

    @staticmethod
    def is_valid_id(tar_int:int) -> tuple:
        """check if 'integer' parameter is a valid identifier value"""
        if not isinstance(tar_int, int):
            return False, {tar_int: "parameter is not a valid [int] value"}
            
        if tar_int > 0:
            return True, {tar_int: f"int:{tar_int} is a valid identifier value"}
        else:
            return False, {tar_int: f"int:{tar_int} isn't a valid identifier value, is less than 0"}


class QR_factory(Signer):

    SECRET = os.environ["QR_SECRET_KEY"]
    QR_PREFIX = "QR"

    def __init__(self, data:str, *args, **kwargs):
        if not data or not isinstance(data, str):
            raise TypeError("'data' parameter is either None or an invalid string format")

        self._data = data
        kwargs["sep"] = "."
        super().__init__(self.SECRET, *args, **kwargs)

    def __repr__(self) -> str:
        return f"QR_factory()"

    @property
    def encode(self) -> str:
        """
        sign <str> data with os.envirion[QR_SIGNER_SECRET] key
        raises TypeError if an invalid string is in 'data' parameter
        return 
        """
        return self.sign(f"{self.QR_PREFIX + self._data}").decode("utf-8")

    @property
    def decode(self) -> Union[int, None]:
        """
        get qrcode data from a valid payload
        return None if the decode fails, otherwise, return 'int' value. (QR-id)
        raises TypeError if an invalid string is in 'payload' parameter
        """
        try:
            unsigned = self.unsign(f"{self._payload}").decode("utf-8") #string
            return int(unsigned[len(self.QR_PREFIX):])

        except (BadSignature, ValueError):
            return None


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

    def __init__(self, parameters:dict={}) -> None:
        """
        create am ErrorMessages instance with a valid dict parameter.
        required parameter structure: {"key1": "error message - content", ... , "key-n": "error message - content"}
        """
        self._parameters = parameters

    @property
    def parameters(self) -> dict:
        return self._parameters

    def __repr__(self) -> str:
        return f'ErrorMessages({self.parameters})'

    def append_parameter(self, new_parameter:dict) -> None:
        """update parameter dict with a new element"""
        if isinstance(new_parameter, str):
            self._parameters.update({new_parameter:"invalid"})

        elif isinstance(new_parameter, dict):
            self._parameters.update(new_parameter)

        else:
            raise AttributeError("invalid [new_parameter] instance")


    def get_response(self, message, status_code):
        """create error response"""
        msg = {"text": message, "parameters": self.parameters}
        return {'msg': msg, 'status_code': status_code}

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

    ITEM_IMG = "https://server.com/default-item.png"
    USER_IMG = "https://server.com/default-user.png"
    COMP_IMG = "https://server.com/default-company.png"
    CURRENCY_DICT = {"name": "US Dollar", "code": "USD", "rate-usd": 1.0}

    def __init__(self):
        self.item_image = self.ITEM_IMG
        self.user_image = self.USER_IMG
        self.company_image = self.COMP_IMG
        self.currency = self.CURRENCY_DICT