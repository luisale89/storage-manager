from flask import abort
import re
from app.utils.exceptions import APIException
from app.utils.helpers import ErrorMessages

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


def validate_email(email: str) -> dict:
    """Valida si una cadena de caracteres tiene un formato de correo electronico válido
    Args:
        email (str): email a validar
    Returns:
        {'error':bool, 'msg':error message}
    """
    if not isinstance(email, str):
        abort(500, "Invalid argument format in <email>, str is expected")

    if len(email) > 320:
        return {"error": True, "msg": "invalid email length, max is 320 chars"}

    #Regular expression that checks a valid email
    ereg = '^[\w]+[\._]?[\w]+[@]\w+[.]\w{2,3}$'
    # ereg = '\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

    if not re.search(ereg, email):
        return {"error":True, "msg": f"invalid email format: <{email}>"}

    return {"error": False, "msg": "ok"}


def validate_pw(password: str) -> dict:
    """Verifica si una contraseña cumple con los parámetros minimos de seguridad
    definidos para esta aplicación.
    Args:
        password (str): contraseña a validar.
    Returns:
        {'error':bool, 'msg':error message}
    """
    if not isinstance(password, str):
        abort(500, "Invalid argument format in <password>, str is expected")

    #Regular expression that checks a secure password
    preg = '^.*(?=.{8,})(?=.*\d)(?=.*[a-z])(?=.*[A-Z]).*$'

    if not re.search(preg, password):
        return {"error": True, "msg": "password is insecure"}

    return {"error": False, "msg": "ok"}


def validate_string(string:str, max_length=None, empty=False) -> dict:
    '''function validates if a string is valid'''

    if not isinstance(string, str):
        return {"error": True, "msg": "invalid string format"}

    if len(string) == 0 and not empty:
        return {"error": True, "msg": "Empty string is invalid"}

    if max_length is not None and isinstance(max_length, int):
        if len(string) > max_length:
            return {"error": True, "msg": f"Input string is too long, {max_length} characters max."}

    return {"error": False, "msg": "ok"}


def validate_inputs(inputs:dict):
    '''function para validar que no existe errores en el diccionario "valid"
    Args: 
        *Dict en formato: 

        {key: {'error':bool, 'msg':error message}} 
        
        donde key es la clave
        del campo que se esta validando. p.ej: email, password, etc..

    Returns:
        pass if ok or raise APIException on any error
    '''
    msg = {}
    invalid = []
    if not isinstance(inputs, dict):
        abort(500, "Invalid argument format in <inputs>, dict is expected")

    for r in inputs.keys():
        if inputs[r]['error']:
            msg[r] = inputs[r]['msg'] #example => email: invalid format...
            invalid.append(r)

    if msg:
        error = ErrorMessages(parameters=invalid, custom_msg='Invalid format in request')
        raise APIException.from_error(error.bad_request)
    
    return None