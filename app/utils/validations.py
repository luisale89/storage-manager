import logging
import re
from app.utils.func_decorators import debug_logger

logger = logging.getLogger(__name__)

@debug_logger(logger)
def validate_id(_id:int) -> int:
    '''
    function that validates if a integer is a valid id. 
    returns integer if is valid
    returns 0 integer if invalid
    '''
    try:
        id = max(0, int(_id)) #id can't be <= 0
    except:
        id = 0
    
    return id


@debug_logger(logger)
def validate_email(email: str) -> tuple:
    """Valida si una cadena de caracteres tiene un formato de correo electronico válido
    Args:
        email (str): email a validar
    Returns tuple:
        (invalid:bool, str:error message)
    """
    if len(email) > 320:
        return (False, "invalid email length, max is 320 chars")

    #Regular expression that checks a valid email
    ereg = '^[\w]+[\._]?[\w]+[@]\w+[.]\w{2,3}$'
    # ereg = '\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

    if not re.search(ereg, email):
        return (False, f"invalid email format: {email}")

    return (True, "email validated")


@debug_logger(logger)
def validate_pw(password: str) -> tuple:
    """Verifica si una contraseña cumple con los parámetros minimos de seguridad
    definidos para esta aplicación.
    Args:
        password (str): contraseña a validar.
    Returns tuple:
        (invalid:bool, str:error message)
    """
    #Regular expression that checks a secure password
    preg = '^.*(?=.{8,})(?=.*\d)(?=.*[a-z])(?=.*[A-Z]).*$'

    if not re.search(preg, password):
        return (False, "password is insecure")

    return (True, "password validated")


@debug_logger(logger)
def validate_string(string:str, max_length=None, empty:bool=False) -> tuple:
    '''function validates if a string is valid
    Args:
        string (str): string a validar.
        max_length: int con el maximo de la string
        empty: bool indicando si la string puede estar vacia.
    Returns tuple:
        (invalid:bool, str:error message)
    '''
    if not isinstance(string, str):
        return (False, "invalid string type format")

    if len(string) == 0 and not empty:
        return (False, "Empty string is invalid")

    if max_length is not None and isinstance(max_length, int):
        if len(string) > max_length:
            return (False, f"Input string is too long, {max_length} characters max.")

    return (True, "string validated")


@debug_logger(logger)
def validate_inputs(inputs:dict) -> tuple:
    '''function para validar que no existe errores en el diccionario "valid"
    Args: 
        *Dict en formato: 
        {key: ('error':bool, 'msg':error message)} 
        
        donde key es la clave
        del campo que se esta validando. p.ej: email, password, etc..
        el mensaje de salida sera la concatenacion de todos los mensajes de las validaciones individuales
        separadas por un -

    Returns tuple:
        ([invalid_items], str:invalid_message)
    '''
    invalids = []
    messages = []

    for key, value in inputs.items():
        valid, msg = value
        if not valid:
            invalids.append(key)
            messages.append(f'[{key}]: {msg}')

    return (invalids, ' | '.join(messages))