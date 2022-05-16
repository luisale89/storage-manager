from flask import Blueprint, current_app

from app.extensions import db
from app.models.main import RoleFunction, Plan
from app.utils.redis_service import redis_client
from app.utils.exceptions import APIException
from app.utils.helpers import JSONResponse
from app.utils.decorators import json_required
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
@json_required()
def api_status_ckeck():

    try:
        db.session.query(RoleFunction).all()
    except SQLAlchemyError as e:
        current_app.logger.error(e)
        raise APIException(message="postgresql service is down", app_result="error", status_code=500)

    try:
        r = redis_client()
        r.ping()
    except:
        current_app.logger.error('redis service is down')
        raise APIException(message="redis service is down", app_result="error", status_code=500)

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