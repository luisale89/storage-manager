from flask import Blueprint, current_app

from app.extensions import db
from app.models.main import RoleFunction, Plan
from app.utils.redis_service import redis_client
from app.utils.exceptions import APIException
from app.utils.helpers import ErrorMessages, JSONResponse
from app.utils.route_decorators import json_required
from sqlalchemy.exc import SQLAlchemyError

manage_bp = Blueprint('manage_bp', __name__)

#*1
@manage_bp.route('/set-globals', methods=['GET']) #!debug
@json_required()
# @super_user_required()
def set_app_globals():

    RoleFunction.add_default_functions()
    Plan.add_default_plans()
    resp = JSONResponse("defaults added")
    return resp.to_json()

#*2
@manage_bp.route('/app-status', methods=['GET'])
def api_status_ckeck():

    error = ErrorMessages()
    error.custom_msg = ""
    try:
        db.session.query(RoleFunction).first()
    except SQLAlchemyError as e:
        error.parameters.append("main-database")
        error.custom_msg += f"[main-database]: {e} | "

    try:
        r = redis_client()
        r.ping()
    except:
        error.parameters.append("redis-service")
        error.custom_msg += f"[redis-service]: redis service is down"

    if error.parameters:
        raise APIException.from_error(error.service_unavailable)

    resp = JSONResponse("app online")
    return resp.to_json()

#*3
@manage_bp.route("/site-map")
def site_map():
    links = []
    for rule in current_app.url_map.iter_rules():

        methods = list(map(lambda x: x, filter(lambda y: y in ['GET', 'POST', 'PUT', 'DELETE'], rule.methods)))
        links.append(f'{str(rule)} - methods: {str(methods)}')
    
    links.sort()
    return JSONResponse(message='ok', payload={'api-endpoints': list(map(lambda x: x, links))}).to_json()