import os
from flask import Flask
#blueprints
from app.blueprints.api_v1 import (
    app_management, auth, user, status, storages, items
)

#extensions
from app.extensions import (
    assets, migrate, jwt, db, cors
)

#utils
from app.utils.exceptions import (
    APIException
)
from app.utils.helpers import JSONResponse
from app.utils.redis_service import redis_client
from werkzeug.exceptions import HTTPException

def create_app(test_config=None):
    ''' Application-Factory Pattern '''
    app = Flask(__name__)
    if test_config == None:
        app.config.from_object(os.environ['APP_SETTINGS'])
    
    #error hanlders
    app.register_error_handler(HTTPException, handle_http_error)
    app.register_error_handler(APIException, handle_API_Exception)
        
    #extensions
    db.init_app(app)
    assets.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    cors.init_app(app, resources={r"/api/*": {"origins": "*"}})

    #API BLUEPRINTS
    app.register_blueprint(auth.auth_bp, url_prefix='/api/v1/auth')
    app.register_blueprint(user.user_bp, url_prefix='/api/v1/user')
    app.register_blueprint(status.status_bp, url_prefix='/api/v1/status')
    app.register_blueprint(app_management.manage_bp, url_prefix='/api/v1/manage')
    app.register_blueprint(storages.storages_bp, url_prefix='/api/v1/storages')
    app.register_blueprint(items.items_bp, url_prefix='/api/v1/items')

    return app


def handle_http_error(e):
    resp = JSONResponse(message=str(e), status_code=e.code, app_result='error')
    return resp.to_json()


def handle_API_Exception(exception): #exception == APIException
    return exception.to_json()


#callbacks
@jwt.token_in_blocklist_loader #check if a token is stored in the blocklist db.
def check_if_token_revoked(jwt_header, jwt_payload):
    jti = jwt_payload['jti']
    r = redis_client()

    try:
        token_in_redis = r.get(jti)
    except:
        raise APIException("connection error with redis service", status_code=500)

    return token_in_redis is not None


@jwt.revoked_token_loader
@jwt.expired_token_loader
def expired_token_msg(jwt_header, jwt_payload):
    rsp = JSONResponse(
        message="token has been revoked or has expired",
        app_result="error",
        payload={"invalid": "jwt"},
        status_code=401
    )
    return rsp.to_json()


@jwt.invalid_token_loader
def invalid_token_msg(error):
    rsp = JSONResponse(
        message=error,
        app_result="error",
        payload={"invalid": "jtw"},
        status_code=401
    )
    return rsp.to_json()


@jwt.unauthorized_loader
def missing_token_msg(error):
    rsp = JSONResponse(
        message=error,
        app_result="error",
        payload={"invalid": "jwt"},
        status_code=401
    )
    return rsp.to_json()