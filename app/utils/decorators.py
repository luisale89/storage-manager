import functools
from flask import request
from app.utils.exceptions import (
    APIException
)
from flask_jwt_extended import verify_jwt_in_request, get_jwt
from app.utils.db_operations import get_user_by_id


#decorator to be called every time an endpoint is reached
def json_required(required:dict=None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper_func(*args, **kwargs):
            if not request.is_json:
                raise APIException("Missing <'content-type': 'application/json'> in header request")

            if request.method == 'PUT' or request.method == 'POST': #body is present only in POST and PUT requests
                _json = request.get_json(silent=True)

                try:
                    _json.items()
                except AttributeError:
                    raise APIException(f"Invalid JSON format in request body - received: <{_json}>")

                if required is not None:
                    missing = [r for r in required.keys() if r not in _json]

                    if missing:
                        raise APIException(f"Missing arguments in body params", payload={"missing": missing})
                    
                    wrong_types = [r for r in required.keys() if not isinstance(_json[r], required[r])] if _json is not None else None
                    if wrong_types:
                        param_types = {k: str(v) for k, v in required.items()}
                        raise APIException("Data types in the JSON request doesn't match the required format", payload={"required": param_types})
                
                kwargs['body'] = _json #!
            return func(*args, **kwargs)
        return wrapper_func
    return decorator


#decorator to grant access to general users.
def user_required(with_company:bool = False):
    def wrapper(fn):
        @functools.wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get('user_access_token'):
                kwargs['user'] = get_user_by_id(claims.get('user_id', None), with_company) #!
                return fn(*args, **kwargs)
            else:
                raise APIException("user-level access token required for this endpoint")

        return decorator
    return wrapper


#decorator to grant access to get user verifications.
def verification_token_required():
    def wrapper(fn):
        @functools.wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get('verification_token'):
                kwargs['claims'] = claims #!
                return fn(*args, **kwargs)
            else:
                raise APIException("verification access token required for this endpoint")

        return decorator
    return wrapper

#decorator to grant access to verificated users only.
def verified_token_required():
    def wrapper(fn):
        @functools.wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get('verified_token'):
                kwargs['claims'] = claims #!
                return fn(*args, **kwargs)
            else:
                raise APIException("invalid access token - User level required")

        return decorator
    return wrapper

#decorator to grant access to super users.
def super_user_required():
    def wrapper(fn):
        @functools.wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get('super_user'):
                kwargs['super_user'] = get_user_by_id(claims.get('user_id', None)) #!
                return fn(*args, **kwargs)
            else:
                raise APIException("invalid access token - Super-User level required", status_code=401)

        return decorator
    return wrapper