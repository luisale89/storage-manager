import logging
import re
from app.utils.exceptions import APIException
from app.utils.helpers import ErrorMessages

logger = logging.getLogger(__name__)

def validate_email(email: str) -> dict:
    """Valida si una cadena de caracteres tiene un formato de correo electronico válido
    Args:
        email (str): email a validar
    Returns:
        {'error':bool, 'msg':error message}
    """
    logger.debug(f'input email: {email}')
    if not isinstance(email, str):
        logger.error(f'invalid email format - str is expected')
        raise TypeError("Invalid argument format, str is expected")

    if len(email) > 320:
        logger.debug(f'email is too long: {len(email)} chars')
        return {"error": True, "msg": "invalid email length, max is 320 chars"}

    #Regular expression that checks a valid email
    ereg = '^[\w]+[\._]?[\w]+[@]\w+[.]\w{2,3}$'
    # ereg = '\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

    if not re.search(ereg, email):
        logger.debug(f'email not detected with regular expression')
        return {"error":True, "msg": f"invalid email format: <{email}>"}

    logger.debug(f'email validated')
    return {"error": False, "msg": "ok"}


def validate_pw(password: str) -> dict:
    """Verifica si una contraseña cumple con los parámetros minimos de seguridad
    definidos para esta aplicación.
    Args:
        password (str): contraseña a validar.
    Returns:
        {'error':bool, 'msg':error message}
    """
    logger.debug(f'Input password: {password}')
    if not isinstance(password, str):
        logger.error(f'Invalid argument format, str is expected')
        raise TypeError("Invalid argument format, str is expected")
    #Regular expression that checks a secure password
    preg = '^.*(?=.{8,})(?=.*\d)(?=.*[a-z])(?=.*[A-Z]).*$'
    if not re.search(preg, password):
        logger.debug('password not detected with regular expression')
        return {"error": True, "msg": "password is insecure"}

    logger.debug('password is valid')
    return {"error": False, "msg": "ok"}


def validate_string(string:str, max_length=None, empty=False) -> dict:

    logger.debug(f'input string: {string} with max_length:{max_length} and empty_accepted:{empty}')

    if not isinstance(string, str):
        logger.debug(f'invalid string format')
        return {"error": True, "msg": "invalid string format"}

    if len(string) == 0 and not empty:
        logger.debug(f'empty string detected')
        return {"error": True, "msg": "Empty string is invalid"}

    if max_length is not None and isinstance(max_length, int):
        if len(string) > max_length:
            logger.debug('string length > max_lenght parameter')
            return {"error": True, "msg": f"Input string is too long, {max_length} characters max."}

    logger.debug('string is valid')
    return {"error": False, "msg": "ok"}


def only_letters(string:str, spaces:bool=False, max_length=None) -> dict:
    """Funcion que valida si un String contiene solo letras
    Se incluyen letras con acentos, ñ. Se excluyen caracteres especiales
    y numeros.
    Args:
        * string (str): cadena de caracteres a evaluar.
        * spaces (bool, optional): Define si la cadena de caracteres lleva o no espacios en blanco. 
        Defaults to False.
    Returns:
        {'error':bool, 'msg':error message}
    """
    logger.debug(f'input string: {string} with spaces: {spaces} and max_length: {max_length}')
    #regular expression that checks only letters string
    sreg = '^[a-zA-ZñáéíóúÑÁÉÍÓÚ]*$'
    #regular expression that check letters and spaces in a string
    sregs = '^[a-zA-Z ñáéíóúÑÁÉÍÓÚ]*$'
    if not isinstance(string, str):
        logger.debug('input is not an instance of string')
        return {"error": True, "msg": f"Input: <{string}> is not a valid string"}

    if not isinstance(spaces, bool):
        logger.error('Invalid argument format, bool is expected')
        raise TypeError("Invalid argument format, bool is expected")

    if max_length is not None and isinstance(max_length, int):
        if len(string) > max_length:
            logger.debug('String is too long')
            return {"error": True, "msg": "String is too long, {} length is allowed".format(max_length)}
    
    if spaces:
        if not re.search(sregs, string):
            # raise APIException("Only letter is valid in str, {} was passed".format(string))
            logger.debug('string contains not only letters')
            return {"error": True, "msg": f"String: <{string}> must include only letters"}
    else: 
        if not re.search(sreg, string):
            # raise APIException("Only letter and no spaces is valid in str, {} was passed".format(string))
            logger.debug('string contains spaces or not only letters')
            return {"error": True, "msg": f"String: <{string}> must include only letters and no spaces"}

    logger.debug('string is valid')
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
    if not isinstance(inputs, dict):
        logger.error('invalid argument format, dict is expected')
        raise TypeError("Invalid argument format, dict is expected")

    for r in inputs.keys():
        if inputs[r]['error']:
            msg[r] = inputs[r]['msg'] #example => email: invalid format...

    if msg:
        raise APIException(f'{ErrorMessages().invalidFormat()}', payload={'invalid': msg})

    return None