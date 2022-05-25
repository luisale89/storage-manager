import logging
import functools
from flask import request, abort
from app.utils.exceptions import (
    APIException
)
from app.models.main import User, Role
from app.utils.helpers import ErrorMessages
from flask_jwt_extended import verify_jwt_in_request, get_jwt

logger = logging.getLogger(__name__)
#decorator to be called every time an endpoint is reached
def json_required(required:dict=None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper_func(*args, **kwargs):
            if not request.is_json:
                raise APIException("Missing <'content-type': 'application/json'> in header request")
            
            if request.method in ['PUT', 'POST']: #body is present only in POST and PUT requests
                _json = request.get_json(silent=True)

                try:
                    _json.items()
                except AttributeError:
                    raise APIException(f"Invalid JSON format in request body - received: <{_json}>")

                if required is not None:
                    missing = [r for r in required.keys() if r not in _json]
                    error = ErrorMessages()
                    if missing:
                        error.parameters = missing
                        error.custom_msg = 'Missing parameters in request'
                        raise APIException.from_error(error.bad_request)
                    
                    wrong_types = [r for r in required.keys() if not isinstance(_json[r], required[r])] if _json is not None else None
                    if wrong_types:
                        error.parameters = wrong_types
                        error.custom_msg = 'Invalid parameter format in request body'
                        raise APIException.from_error(error.bad_request)
                
                kwargs['body'] = _json #!
            return func(*args, **kwargs)
        return wrapper_func
    return decorator


#decorator to grant access to general users.
def role_required(level:int=99): #user level for any endpoint
    def wrapper(fn):
        @functools.wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()

            if claims.get('role_access_token', False):
                role_id = claims.get('role_id', None)
                if role_id is None:
                    abort(500, "role_id not present in jwt")

                role = Role.get_role_by_id(role_id)
                if role is None or not role._isActive:
                    raise APIException.from_error(ErrorMessages(parameters='user-role').unauthorized)

                if role.role_function.level > level:
                    raise APIException.from_error(ErrorMessages(parameters='role-level').unauthorized)
                    
                kwargs['role'] = role
                return fn(*args, **kwargs)
            else:
                raise APIException.from_error(
                    ErrorMessages(parameters='role-level', custom_msg='role-level access token required for this endpoint').unauthorized
                )

        return decorator
    return wrapper


def user_required():
    def wrapper(fn):
        @functools.wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()

            if claims.get("user_access_token", False):
                user_id = claims.get('user_id', None)
                if user_id is None:
                    abort(500, "user_id not present in jwt")

                user = User.get_user_by_id(user_id)
                if user is None:
                    raise APIException.from_error(ErrorMessages(parameters='email').notFound)

                elif not user._signup_completed or not user._email_confirmed:
                    raise APIException.from_error(ErrorMessages(parameters='email').unauthorized)
                
                kwargs['user'] = user
                return fn(*args, **kwargs)
            
            else:
                raise APIException.from_error(
                    ErrorMessages(parameters='role-level', custom_msg='role-level access token required for this endpoint').unauthorized
                )

        return decorator
    return wrapper


#decorator to grant access to get user verifications.
def verification_token_required():
    def wrapper(fn):
        @functools.wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get('verification_token', False):
                kwargs['claims'] = claims #!
                return fn(*args, **kwargs)
            else:
                raise APIException.from_error(ErrorMessages(parameters='jwt', custom_msg='verification-jwt-required').unauthorized)

        return decorator
    return wrapper

#decorator to grant access to verificated users only.
def verified_token_required():
    def wrapper(fn):
        @functools.wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get('verified_token', False):
                kwargs['claims'] = claims #!
                return fn(*args, **kwargs)
            else:
                raise APIException.from_error(ErrorMessages(parameters='jwt', custom_msg='verified-jwt-required').unauthorized)

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
                kwargs['super_user'] = User.get_user_by_id(claims.get('user_id', None)) #!
                return fn(*args, **kwargs)
            else:
                raise APIException("invalid access token - Super-User level required", status_code=401)

        return decorator
    return wrapper


def log_decorator(my_logger):
    def wrapper(func):
        @functools.wraps(func)
        def decorator(*args, **kwargs):
            args_repr = [repr(a) for a in args]
            kwargs_repr = [f"{k}={v!r}" for k, v in kwargs.items()]
            signature = ", ".join(args_repr + kwargs_repr)

            my_logger.debug(f"function {func.__name__} called with args {signature}")
            response = func(*args, **kwargs)
            my_logger.debut(f"return {response}")

            return response
        return decorator
    return wrapper