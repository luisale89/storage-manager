from flask import Blueprint
import os

from app.models.main import RoleFunction, Plan, Role
from app.utils.redis_service import redis_client
from app.utils.exceptions import APIException
from app.utils.helpers import JSONResponse
from app.utils.decorators import (json_required, super_user_required)

manage_bp = Blueprint('manage_bp', __name__)


@manage_bp.route('/set-globals', methods=['GET']) #!debug
@json_required()
# @super_user_required()
def set_app_globals():

    RoleFunction.add_default_functions()
    Plan.add_default_plans()
    resp = JSONResponse("defaults added")
    return resp.to_json()


@manage_bp.route('/app-status', methods=['GET'])
@json_required()
def api_status_ckeck():

    try:
        Role.query.get(1)
    except:
        raise APIException(message="postgresql service is down", app_result="error", status_code=500)

    try:
        r = redis_client()
        r.ping()

    except:
        raise APIException(message="redis service is down", app_result="error", status_code=500)

    resp = JSONResponse("app online")
    return resp.to_json()