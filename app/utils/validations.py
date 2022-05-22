import logging
from flask import abort
import re
from app.utils.exceptions import APIException
from app.utils.helpers import ErrorMessages

logger = logging.getLogger(__name__)

def validate_id(_id:int) -> int:
    '''
    function that validates if a integer is a valid id. 
    returns integer if is valid
    returns 0 integer if invalid
    '''
    logger.info(f'validate_id({_id})')
    try:
        id = max(0, int(_id)) #id can't be <= 0
    except:
        logger.info(f"can't convert {_id} to integer")
        id = 0
    
    logger.info(f'return id:{id}')
    return id


def validate_email(email: str) -> dict:
    """Valida si una cadena de caracteres tiene un formato de correo electronico válido
    Args:
        email (str): email a validar
    Returns:
        {'error':bool, 'msg':error message}
    """
    logger.info(f"validate_email({email})")
    if not isinstance(email, str):
        abort(500, "Invalid argument format in <email>, str is expected")

    if len(email) > 320:
        logger.debug(f'email is too long | {len(email)} chars')
        return {"error": True, "msg": "invalid email length, max is 320 chars"}

    #Regular expression that checks a valid email
    ereg = '^[\w]+[\._]?[\w]+[@]\w+[.]\w{2,3}$'
    # ereg = '\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

    if not re.search(ereg, email):
        logger.info(f'email is invalid')
        return {"error":True, "msg": f"invalid email format: <{email}>"}

    logger.info(f'email is valid')
    return {"error": False, "msg": "ok"}


def validate_pw(password: str) -> dict:
    """Verifica si una contraseña cumple con los parámetros minimos de seguridad
    definidos para esta aplicación.
    Args:
        password (str): contraseña a validar.
    Returns:
        {'error':bool, 'msg':error message}
    """
    logger.info(f"validate_pw()")
    if not isinstance(password, str):
        abort(500, "Invalid argument format in <password>, str is expected")

    #Regular expression that checks a secure password
    preg = '^.*(?=.{8,})(?=.*\d)(?=.*[a-z])(?=.*[A-Z]).*$'

    if not re.search(preg, password):
        logger.info('invalid password')
        return {"error": True, "msg": "password is insecure"}

    logger.info(f'valid password')
    return {"error": False, "msg": "ok"}


def validate_string(string:str, max_length=None, empty=False) -> dict:
    '''function validates if a string is valid'''

    logger.info(f'validate_string(length={max_length}, empty={empty})')
    if not isinstance(string, str):
        logger.info(f'invalid string format')
        return {"error": True, "msg": "invalid string format"}

    if len(string) == 0 and not empty:
        logger.info(f'empty string detected')
        return {"error": True, "msg": "Empty string is invalid"}

    if max_length is not None and isinstance(max_length, int):
        logger.debug(f'length: {len(string)}')
        if len(string) > max_length:
            logger.info(f'string length > {max_length}')
            return {"error": True, "msg": f"Input string is too long, {max_length} characters max."}

    logger.info(f'string is valid')
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
    logger.info(f'validate_inputs()')
    msg = {}
    if not isinstance(inputs, dict):
        abort(500, "Invalid argument format in <inputs>, dict is expected")

    for r in inputs.keys():
        if inputs[r]['error']:
            msg[r] = inputs[r]['msg'] #example => email: invalid format...

    if msg:
        raise APIException(f'{ErrorMessages().invalidFormat()}', payload={'invalid': msg})
    logger.info("inputs validated")
    return None