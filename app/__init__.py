import os
import logging
from flask import Flask, request, abort
#blueprints
from app.blueprints.api_v1 import (
    app_management, auth, user, storages, items, company
)
from sqlalchemy.exc import DBAPIError

#extensions
from app.extensions import (
    assets, migrate, jwt, db, cors
)

#utils
from app.utils.exceptions import (
    APIException
)
from app.utils.helpers import JSONResponse, _epoch_utc_to_datetime
from app.utils.redis_service import redis_client
from werkzeug.exceptions import HTTPException, InternalServerError

logger = logging.getLogger(__name__)

def create_app(test_config=None):
    ''' Application-Factory Pattern '''
    app = Flask(__name__)
    if test_config == None:
        app.config.from_object(os.environ['APP_SETTINGS'])
    
    #error hanlders
    app.register_error_handler(HTTPException, handle_http_error)
    app.register_error_handler(APIException, handle_API_Exception)
    app.register_error_handler(InternalServerError, handle_internal_server_error)
    app.register_error_handler(DBAPIError, handle_DBAPI_disconnect)
        
    #extensions
    configure_logger(app)
    db.init_app(app)
    assets.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

    #API BLUEPRINTS
    app.register_blueprint(auth.auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(user.user_bp, url_prefix='/api/v1/user')
    app.register_blueprint(app_management.manage_bp, url_prefix='/api/v1/manage')
    app.register_blueprint(storages.storages_bp, url_prefix='/api/v1/storages')
    app.register_blueprint(items.items_bp, url_prefix='/api/v1/items')
    app.register_blueprint(company.company_bp, url_prefix='/api/v1/company')

    return app

def handle_DBAPI_disconnect(e):
    logger.error(f'DBAPIError: {e}')
    resp = JSONResponse(message=str(e), payload={'error': 'main-database'},status_code=503, app_result='error')
    return resp.to_json()


def handle_http_error(e):
    logger.info(f'HTTPError: {e} | path: {request.path}')
    resp = JSONResponse(message=str(e), status_code=e.code, app_result='error')
    return resp.to_json()


def handle_internal_server_error(e):
    logger.error(f'Internal server error: {e} | path: {request.method} {request.path} | body: {request.get_json(silent=True)} args: {request.args}', exc_info=True)
    resp = JSONResponse(message=str(e), status_code=500, app_result='error')
    return resp.to_json()


def handle_API_Exception(exception): #exception == APIException
    return exception.to_json()


#callbacks
@jwt.token_in_blocklist_loader #check if a token is stored in the blocklist db.
def check_if_token_revoked(jwt_header, jwt_payload):
    jti = jwt_payload['jti']
    r = redis_client()
    logger.debug("check_if_token_revoked()")
    try:
        token_in_redis = r.get(jti)
    except:
        abort(503, "redis-service is down")

    return token_in_redis is not None


@jwt.revoked_token_loader
@jwt.expired_token_loader
def expired_token_msg(jwt_header, jwt_payload):
    exp = _epoch_utc_to_datetime(jwt_payload['exp'])
    rsp = JSONResponse(
        message="token has been revoked or has expired",
        app_result="error",
        status_code=401
    )
    return rsp.to_json()


@jwt.invalid_token_loader
def invalid_token_msg(error):
    rsp = JSONResponse(
        message=error,
        app_result="error",
        status_code=401
    )
    return rsp.to_json()


@jwt.unauthorized_loader
def missing_token_msg(error):
    rsp = JSONResponse(
        message=error,
        app_result="error",
        status_code=401
    )
    return rsp.to_json()


def configure_logger(app):
    #se eliminan los manejadores que se hayan creado al momento.
    del app.logger.handlers[:]
    loggers = [app.logger, ]
    handlers = []

    #manejador para escribir mensajes en consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(verbose_formatter())

    if app.config.get('TESTING', False) or app.config.get('DEBUG', False):
        console_handler.setLevel(logging.DEBUG)
        handlers.append(console_handler)

    else: #production_env
        console_handler.setLevel(logging.INFO)
        handlers.append(console_handler)

    for l in loggers:
        for handler in handlers:
            l.addHandler(handler)
        l.propagate=False
        l.setLevel(logging.DEBUG) #Level of the logger


def verbose_formatter():
    return logging.Formatter(
        '[%(asctime)s.%(msecs)d] %(levelname)s [%(name)s] [%(funcName)s:%(lineno)d] %(message)s',
        datefmt='%d/%m/%Y %H:%M:%S'
    )