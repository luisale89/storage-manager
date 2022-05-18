import logging
from datetime import datetime
from dateutil.parser import parse, ParserError
from datetime import timezone
from random import sample
import string

from flask import jsonify

logger = logging.getLogger(__name__)

def _epoch_utc_to_datetime(epoch_utc):
    """
    Helper function for converting epoch timestamps into
    python datetime objects.
    """
    response = datetime.fromtimestamp(epoch_utc)
    logger.debug(f'input: {epoch_utc} | output: {response}')

    return response


def str_to_int(string):
    '''helper function to convert a string into an integer.. return None if is not posible the conversion'''
    try:
        integer = int(string)
    except:
        logger.debug(f"invalid string:{string}, can't be converted to an integer value")
        integer = None

    logger.debug(f'input: {string}-{type(string)} | output: {integer}-{type(integer)}')
    return integer


def random_password(length:int=16) -> str:
    '''
    function creates a random password, default length is 16 characters. pass in required length as an integer parameter
    '''
    logger.debug(f'required random password with lengh={length}')
    if not isinstance(length, int):
        logger.error(f'invalid length parameter - received: {type(length)}')
        raise TypeError('invalid format for length paramter, <int> is required')

    lower = string.ascii_lowercase
    upper = string.ascii_uppercase
    nums = string.digits
    symbols = string.punctuation

    all = lower + upper + nums + symbols
    password = "".join(sample(all, length))

    logger.debug(f'password: {password}')
    return password


def normalize_datetime(raw_date:datetime) -> datetime:
    '''
    Helper function for normalize datetime and store them in the database.
    The normalized datetime is naive, and utc based
    '''
    try:
        dt = parse(raw_date)
        if dt.tzinfo is not None: #if a timezone info has been passed in
            date = dt.astimezone(timezone.utc).replace(tzinfo=None) #store the date as naive datetime..
        else:
            date = dt
    except ParserError:
        logger.debug(f'error parsing datetime: {raw_date}')
        date = None

    logger.debug(f'input: {raw_date} output: {date}')
    return date


def datetime_formatter(datetime:datetime) -> str:
    '''
    returns a string that represents datetime stored in database, in UTC timezone

    datetime representation format: %Y-%m-%dT%H:%M:%S%z

    * Parameters:
    <datetime> a valid datetime instance
    '''
    response = datetime.strftime("%Y-%m-%dT%H:%M:%SZ")
    logger.debug(f'input: {datetime} | output: {response}')

    return response


def normalize_string(string: str, spaces=False) -> str:
    """Normaliza una cadena de caracteres a palabras con Mayúsculas y sin/con espacios.
    Args:
        name (str): Cadena de caracteres a normalizar.
        spaces (bool, optional): Indica si la cadena de caracteres incluye o no espacios. 
        Defaults to False.
    Returns:
        str: Candena de caracteres normalizada.
    """
    if not isinstance(string, str):
        logger.error(f"invalid string parameter: {string} received")
        raise TypeError("Invalid name argument, string is expected")

    if not isinstance(spaces, bool):
        logger.error(f"invalid spaces parameter: {spaces} received")
        raise TypeError("Invalid spaces argunment, bool is expected")

    response = ''
    if not spaces:
        response = string.replace(" ", "")
    else:
        response = string.strip()

    logger.debug(f"input: <{string}> | output: <{response}>")
    return response


class JSONResponse():

    '''
    Class
    Genera mensaje de respuesta a las solicitudes JSON. los parametros son:

    - message: Mesanje a mostrar al usuario.
    - app_result = "success", "error"
    - status_code = http status code
    - payload = dict con cualquier informacion que se necesite enviar al usuario.

    methods:

    - serialize() -> return dict
    - to_json() -> http JSON response

    '''

    def __init__(self, message="ok", app_result="success", status_code=200, payload=None):
        self.app_result = app_result
        self.status_code = status_code
        self.data = payload
        self.message = message

    def serialize(self):
        rv = {
            "result": self.app_result,
            "data": dict(self.data or ()),
            "message": self.message
        }
        return rv

    def to_json(self):
        return jsonify(self.serialize()), self.status_code


class ErrorMessages():

    def __init__(self, expected:str='', arg:str=''):
        self.dbError = "An error was raised while operating with the database"
        self.invalidInput = "Invalid parameters in request body - no match with posible inputs"
        self.conflict = "Parameter already exists:"
        self.dateFormat = "Invalid datetime format in parameter:"
        self.invalidSearch = "Invalid search parameter:"
        self.invalidID = "Invalid id parameter, expected integer >= 1"
        self.expected = expected
        self.arg = arg

    def notFound(self):
        return f'parameter <{self.expected}> not found in database'

    def invalidFormat(self):
        return f'Invalid format in request, expected format: <{self.expected}> in argument: <{self.arg}>'


class DefaultContent():

    def __init__(self):
        self.item_image = "https://server.com/default-item.png"
        self.user_image = "https://server.com/default-user.png"
        self.company_image = "https://server.com/default-company.png"
        self.currency = {"name": "US Dollar", "code": "USD", "rate-usd": 1.0}