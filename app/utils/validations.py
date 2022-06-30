import logging
import re
from app.utils.func_decorators import app_logger

logger = logging.getLogger(__name__)


@app_logger(logger)
def validate_id(_id: int) -> int:
    """
    function that validates if an integer is a valid id.
    Args:
        _id (int): id to validate
    returns int:
        int > 0 if the id is valid
        int = 0 if the id is invalid
    """
    try:
        valid = max(0, int(_id))  # id can't be <= 0
    except Exception:
        valid = 0

    return valid


@app_logger(logger)
def validate_email(email: str) -> tuple:
    """
    Validates if a character string has a valid email format
    Args:
        email (str): email to validate
    Returns tuple:
        (valid:bool, str:error message)
            valid=True if the email is valid
            valid=False if the email is invalid
    """
    if len(email) > 320:
        return False, "invalid email length, max is 320 chars"

    # Regular expression that checks a valid email
    ereg = '^[\w]+[\._]?[\w]+[@]\w+[.]\w{2,3}$'
    # ereg = '\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'

    if not re.search(ereg, email):
        return False, f"invalid email format: {email}"

    return True, "email validated"


@app_logger(logger)
def validate_pw(password: str) -> tuple:
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

    if not re.search(preg, password):
        return False, "password is insecure"

    return True, "password validated"


@app_logger(logger)
def validate_string(string: str, max_length: int = None, empty: bool = False) -> tuple:
    """
    function validates if a string is valid
    Args:
        string (str): string to validate.
        max_length (int): max length of the string.
        empty (bool): True if the string could be empty.
    Returns:
        (invalid:bool, str:error message)
    """
    if not isinstance(string, str):
        return False, "invalid string type format"

    if len(string) == 0 and not empty:
        return False, "Empty string is invalid"

    if max_length is not None and isinstance(max_length, int):
        if len(string) > max_length:
            return False, f"Input string is too long, {max_length} characters max."

    return True, "string validated"


@app_logger(logger)
def validate_inputs(inputs: dict) -> tuple:
    """
    function to validate that there are no errors in the "inputs" dictionary
    Args:
        inputs (dict): inputs to validate following the format:
            {key: ('error':bool, 'msg':error message)}

        where key is the `key` of the field that is validating. example: email, password, etc.
        the output message will be the sum of all the individual messages separated by a |

    Returns tuple:
        ([invalid_items], str:invalid_message)
    """
    invalids = []
    messages = []

    for key, value in inputs.items():
        valid, msg = value
        if not valid:
            invalids.append(key)
            messages.append(f'[{key}]: {msg}')

    return invalids, ' | '.join(messages)
