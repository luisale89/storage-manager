import logging
import functools
from flask import request, abort
from app.utils.exceptions import (
    APIException
)
from app.utils.helpers import ErrorMessages
from app.utils.route_helper import valid_id
from flask_jwt_extended import verify_jwt_in_request, get_jwt
from app.utils.db_operations import get_role_by_id, get_user_by_id
from app.utils.redis_service import add_jwt_to_blocklist

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

                    if missing:
                        logger.debug("missing parameters in request")
                        raise APIException(f"Missing arguments in body params", payload={"missing": missing})
                    
                    wrong_types = [r for r in required.keys() if not isinstance(_json[r], required[r])] if _json is not None else None
                    if wrong_types:
                        logger.debug("wrong types parameters in request")
                        param_types = {k: str(v) for k, v in required.items()}
                        raise APIException("Data types in the JSON request doesn't match the required format", payload={"required": param_types})
                
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

                role = get_role_by_id(valid_id(role_id))
                if role is None:
                    raise APIException("role does not exists", status_code=403)
                elif not role._isActive:
                    raise APIException("role has been disabled", status_code=403)

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

                user = get_user_by_id(valid_id(user_id))
                if user is None:
                    raise APIException(ErrorMessages("user_id").notFound(), 404)
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
                kwargs['super_user'] = get_user_by_id(claims.get('user_id', None)) #!
                return fn(*args, **kwargs)
            else:
                raise APIException("invalid access token - Super-User level required", status_code=401)

        return decorator
    return wrapper