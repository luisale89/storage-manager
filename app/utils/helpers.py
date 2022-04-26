from datetime import datetime
from dateutil.parser import parse, ParserError
from datetime import timezone
import uuid

from flask import jsonify


def _epoch_utc_to_datetime(epoch_utc):
    """
    Helper function for converting epoch timestamps into
    python datetime objects.
    """
    return datetime.fromtimestamp(epoch_utc)


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
        date = None
    
    return date


def datetime_formatter(datetime:datetime) -> str:
    '''
    returns a string that represents datetime stored in database, in UTC timezone

    datetime representation format: %Y-%m-%dT%H:%M:%S%z

    * Parameters:
    <datetime> a valid datetime instance
    '''
    
    return datetime.strftime("%Y-%m-%dT%H:%M:%SZ")


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
        raise TypeError("Invalid name argument, string is expected")
    if not isinstance(spaces, bool):
        raise TypeError("Invalid spaces argunment, bool is expected")

    if not spaces:
        return string.replace(" ", "").lower()
    else:
        return string.strip().lower()


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

    def __init__(self, message, app_result="success", status_code=200, payload=None):
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


def pagination_form(p_object) -> dict:
    '''
    Receive an pagination object from flask, returns a dict with pagination data, set to return to the user.
    '''
    return {
        "pagination": {
            "pages": p_object.pages,
            "has_next": p_object.has_next,
            "has_prev": p_object.has_prev,
            "current_page": p_object.page
        }
    }

class ErrorMessages():

    def __init__(self):
        self.dbError = "An error was raised while operating with the database"
        self.invalidInput = "Invalid parameters in request body - no match with posible inputs"
        self.notFound = "parameter not found:"
        self.conflict = "Parameter already exists:"
        self.dateFormat = "Invalid datetime format in parameter:"
        self.invalidSearch = "Invalid search parameter:"


class DefaultContent():

    def __init__(self):
        self.item_image = "https://server.com/default-item.png"
        self.user_image = "https://server.com/default-user.png"
        self.company_image = "https://server.com/default-company.png"
        self.currency = {"name": "US Dollar", "code": "USD", "rate-usd": 1.0}