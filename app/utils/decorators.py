import functools
from flask import request
from app.utils.exceptions import (
    APIException
)
from flask_jwt_extended import verify_jwt_in_request, get_jwt


#decorator to be called every time an endpoint is reached
def json_required(required:dict=None, query_params:bool=False):
    def decorator(func):
        @functools.wraps(func)
        def wrapper_func(*args, **kwargs):
            if not request.is_json:
                raise APIException("Missing header in request" ,payload={"missing":{"content-type":"application/json"}})

            if required is not None:
                _json = request.get_json(silent=True)
                _qparams = request.args

                if query_params:
                    missing = [r for r in required.keys() if r not in _qparams]
                else:             
                    if _json is None:
                        raise APIException("invalid json in request body")
                    missing = [r for r in required.keys() if r not in _json]

                if missing:
                    raise APIException(f"Missing arguments in {'url' if query_params is True else 'query params'}", payload={"missing": missing})
                
                wrong_types = [r for r in required.keys() if not isinstance(_json[r], required[r])] if _json is not None else None
                if wrong_types:
                    param_types = {k: str(v) for k, v in required.items()}
                    raise APIException("Data types in the request JSON doesn't match the required format", payload={"required": param_types})

            return func(*args, **kwargs)
        return wrapper_func
    return decorator


#decorator to grant access to general users.
def user_required():
    def wrapper(fn):
        @functools.wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get('user_access_token'):
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
                return fn(*args, **kwargs)
            else:
                raise APIException("verified access token required for this endpoint")

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
                return fn(*args, **kwargs)
            else:
                raise APIException("super-user access token required for this endpoint", status_code=401)

        return decorator
    return wrapper