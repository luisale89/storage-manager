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
                        logger.info(error.MISSING_ARGS)
                        raise APIException(error.MISSING_ARGS, payload={error.STATUS_400: missing})
                    
                    wrong_types = [r for r in required.keys() if not isinstance(_json[r], required[r])] if _json is not None else None
                    if wrong_types:
                        logger.info(error.invalidFormat)
                        raise APIException(error.invalidFormat, payload={error.STATUS_400: wrong_types})
                
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
            logger.info(f"role_required(level={level})")

            if claims.get('role_access_token'):
                role_id = claims.get('role_id', None)
                if role_id is None:
                    abort(500, "role_id not present in jwt")

                role = Role.get_role_by_id(role_id)
                if role is None or not role._isActive:
                    raise APIException("role does not exists", status_code=403)

                if role.role_function.level > level:
                    raise APIException("current user has no access to this endpoint", status_code=402)
                    
                logger.info('return role to decorated function')
                kwargs['role'] = role
                return fn(*args, **kwargs)
            else:
                raise APIException("role-level access token required for this endpoint", status_code=401)

        return decorator
    return wrapper


def user_required():
    def wrapper(fn):
        @functools.wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            logger.info('user_required')

            if claims.get("user_access_token"):
                user_id = claims.get('user_id', None)
                if user_id is None:
                    abort(500, "user_id not present in jwt")

                user = User.get_user_by_id(user_id)
                if user is None:
                    error = ErrorMessages("user_id")
                    raise APIException(error.notFound, payload={error.STATUS_404: error.expected}, status_code=404)

                elif not user._signup_completed or not user._email_confirmed:
                    raise APIException("current user has no access to this endpoint", status_code=402)
                
                logger.info("return user to decorated function")
                kwargs['user'] = user
                return fn(*args, **kwargs)
            
            else:
                raise APIException("user-level access token required for this endpoint", status_code=401)

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
                kwargs['super_user'] = User.get_user_by_id(claims.get('user_id', None)) #!
                return fn(*args, **kwargs)
            else:
                raise APIException("invalid access token - Super-User level required", status_code=401)

        return decorator
    return wrapper