import re
from app.utils.exceptions import APIException

def validate_email(email: str) -> dict:
    """Valida si una cadena de caracteres tiene un formato de correo electronico válido
    Args:
        email (str): email a validar
    Returns:
        {'error':bool, 'msg':error message}
    """

    if not isinstance(email, str):
        raise TypeError("Invalid argument format, str is expected")

    if len(email) > 320:
        return {"error": True, "msg": "invalid email length, max is 320 chars"}

    #Regular expression that checks a valid email
    ereg = '^[\w]+[\._]?[\w]+[@]\w+[.]\w{2,3}$'

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
        raise TypeError("Invalid argument format, str is expected")
    #Regular expression that checks a secure password
    preg = '^.*(?=.{8,})(?=.*\d)(?=.*[a-z])(?=.*[A-Z]).*$'
    if not re.search(preg, password):
        return {"error": True, "msg": "password is insecure"}

    return {"error": False, "msg": "ok"}


def validate_string(string:str, max_length=None) -> dict:

    if not isinstance(string, str):
        return {"error": True, "msg": "invalid string format"}
    if len(string) == 0:
        return {"error": True, "msg": "Empty string is invalid"}
    if max_length is not None:
        if len(string) > max_length:
            return {"error": True, "msg": f"Input string is too long, {max_length} characters max."}

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
    
    #regular expression that checks only letters string
    sreg = '^[a-zA-ZñáéíóúÑÁÉÍÓÚ]*$'
    #regular expression that check letters and spaces in a string
    sregs = '^[a-zA-Z ñáéíóúÑÁÉÍÓÚ]*$'
    if not isinstance(string, str):
        return {"error": True, "msg": f"Input: <{string}> is not a valid string"}
    if not isinstance(spaces, bool):
        raise TypeError("Invalid argument format, bool is expected")
    if max_length is not None:
        if len(string) > max_length:
            return {"error": True, "msg": "String is too long, {} length is allowed".format(max_length)}
    
    if spaces:
        if not re.search(sregs, string):
            # raise APIException("Only letter is valid in str, {} was passed".format(string))
            return {"error": True, "msg": f"String: <{string}> must include only letters"}
    else: 
        if not re.search(sreg, string):
            # raise APIException("Only letter and no spaces is valid in str, {} was passed".format(string))
            return {"error": True, "msg": f"String: <{string}> must include only letters and no spaces"}
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
        raise TypeError("Invalid argument format, dict is expected")
    for r in inputs.keys():
        if inputs[r]['error']: 
            msg[r] = inputs[r]['msg']

    if msg:
        raise APIException("invalid input in request", payload={'invalid': msg})

    return None