import logging
import functools
from flask import request, abort
from app.utils.exceptions import (
    APIException
)
from app.models.main import User, Role, Company
from app.utils.helpers import ErrorMessages as EM
from flask_jwt_extended import verify_jwt_in_request, get_jwt

logger = logging.getLogger(__name__)


# decorator to be called every time an endpoint is reached
def json_required(required: dict = None):
    def decorator(func):
        @functools.wraps(func)
        def wrapper_func(*args, **kwargs):
            logger.info(f'[start] {request.method} request @ endpoint {request.url}')
            logger.debug(f'@json_required({required})')
            if not request.is_json:
                raise APIException("Missing 'content-type': 'application/json' in header request")

            if request.method in ['PUT', 'POST']:  # body is present only in POST and PUT requests
                _json = request.get_json(silent=True)
                logger.debug(f'request body: {_json}')
                try:
                    _json.items()
                except AttributeError:
                    raise APIException(f"Invalid JSON format in request body - received: <{_json}>")

                if required is not None:
                    missing = [{r: "not found in request body"} for r in required.keys() if r not in _json]
                    if missing:
                        raise APIException.from_error(EM(missing).bad_request)

                    wrong_types = [{r: f"invalid {required[r].__name__!r} instance"} for r in required.keys() if \
                        not isinstance(_json[r], required[r])] if _json is not None else None
                    if wrong_types:
                        raise APIException.from_error(EM(wrong_types).bad_request)

                kwargs['body'] = _json  # !
            return func(*args, **kwargs)

        return wrapper_func

    return decorator


# decorator to grant access to general users.
def role_required(level: int = 99):  # role-level requiried for the target endpoint
    def wrapper(fn):
        @functools.wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()

            if claims.get('role_access_token', None):
                role_id = claims.get('role_id', None)
                if role_id is None:
                    abort(500, "role_id not present in jwt")

                role = Role.get_role_by_id(role_id)

                if role is None:
                    raise APIException.from_error(EM({"role": f"role-id-{role_id} not found"}).notFound)
                
                if not role.is_enabled or not role.user.is_enabled:
                    raise APIException.from_error(EM({"user": "user-role has been disabled"}).user_not_active)

                if role.role_function.level > level:
                    raise APIException.from_error(EM({"role-level": "current role does not have enough privileges"}).unauthorized)

                kwargs['role'] = role
                return fn(*args, **kwargs)
            else:
                raise APIException.from_error(EM({"role-access-token": "role-level access token required for this endpoint"}).unauthorized)

        return decorator

    return wrapper


def user_required(customer:bool = False):
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
                    raise APIException.from_error(EM({"user": f"user-ID-{user_id} not found"}).notFound)

                elif not user.is_enabled():
                    raise APIException.from_error(EM({"user": "user's email is not validated or signup proccess is not completed"}).unauthorized)

                kwargs['user'] = user

                if customer:
                    if claims.get("customer_access_token", None):
                        company_id = claims.get("company_id", None)
                        if not company_id:
                            abort(500, "company_id not present in jwt")

                        company = Company.get_company_by_id(company_id).first()
                        if not company:
                            raise APIException.from_error(EM({"company_id": f"company-id-{company_id} not found"}).notFound)

                        kwargs["company"] = company

                    else:
                        raise APIException.from_error(EM({"customer": "customer-access-token required for this endpoint"}).unauthorized)

                return fn(*args, **kwargs)

            else:
                raise APIException.from_error(EM({"user": "user-access-token required for this endpoint"}).unauthorized)

        return decorator

    return wrapper


# decorator to grant access to get user verifications.
def verification_token_required():
    def wrapper(fn):
        @functools.wraps(fn)
        def decorator(*args, **kwargs):
            logger.debug(f'@verification_token_required()')
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get('verification_token', False):
                kwargs['claims'] = claims  # !
                return fn(*args, **kwargs)
            else:
                raise APIException.from_error(EM({"jwt": "verification-jwt-required"}).unauthorized)

        return decorator

    return wrapper


# decorator to grant access to verified users only.
def verified_token_required():
    def wrapper(fn):
        @functools.wraps(fn)
        def decorator(*args, **kwargs):
            logger.debug(f'@verified_token_required()')
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get('verified_token', False):
                kwargs['claims'] = claims  # !
                return fn(*args, **kwargs)
            else:
                raise APIException.from_error(EM({"jwt": "verified-jwt-required"}).unauthorized)

        return decorator

    return wrapper


# decorator to grant access to super users.
def super_user_required():
    def wrapper(fn):
        @functools.wraps(fn)
        def decorator(*args, **kwargs):
            verify_jwt_in_request()
            claims = get_jwt()
            if claims.get('super_user'):
                kwargs['super_user'] = User.get_user_by_id(claims.get('user_id', None))  # !
                return fn(*args, **kwargs)
            else:
                raise APIException.from_error(EM({"super-user": "invalid access token - Super-User level required"}).unauthorized)

        return decorator

    return wrapper
