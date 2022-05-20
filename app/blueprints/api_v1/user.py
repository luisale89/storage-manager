from crypt import methods
from flask import Blueprint

#extensions
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError
from flask_jwt_extended import get_jwt

#models
from app.models.main import User

#utils
from app.utils.helpers import JSONResponse
from app.utils.decorators import json_required, user_required
from app.utils.db_operations import handle_db_error, update_row_content
from app.utils.redis_service import add_jwt_to_blocklist
from app.utils.route_helper import valid_id

#models
# from app.models.main import Company, User, Role

user_bp = Blueprint('user_bp', __name__)

#*1
@user_bp.route('/', methods=['GET'])
@json_required()
@user_required(individual=True)
def get_user_profile(role):

    resp = JSONResponse(
        payload={
            "user": role.user.serialize_all()
        })

    return resp.to_json()

#*2
@user_bp.route('/', methods=['PUT'])
@json_required()
@user_required(individual=True)
def update_user_profile(role, body):
    
    to_update = update_row_content(User, body)

    try:
        User.query.filter(User.id == role.user.id).update(to_update)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)
    
    resp = JSONResponse(message="user's profile has been updated")
    return resp.to_json()

#*3
@user_bp.route('/companies/', methods=['GET'])
@json_required()
@user_required(individual=True)
def get_user_roles(role):
    #returns all user's roles, giving information about the role_function and company.

    return JSONResponse(payload={
        "companies": list(map(lambda x: {**x.company.serialize(), "role": x.serialize_all()}, role.user.roles))
    }).to_json()


#*4
@user_bp.route('/companies/<int:company_id>', methods=['DELETE'])
@json_required()
@user_required(individual=True)
def drop_user_role(role, company_id=None):
    #delete target role...
    target_role = valid_id(company_id)
    return JSONResponse('in development...').to_json()

#*5
@user_bp.route('/companies/<int:company_id>/activate', methods=['PUT'])
@json_required()
@user_required(individual=True)
def change_active_role(role, body, company_id=None):
    #returns new jwt with target role in it, and block current jwt...
    return JSONResponse('in development...').to_json()

#*6
@user_bp.route('/logout', methods=['DELETE']) #logout user
@json_required()
@user_required(individual=True)
def logout(role):
    """
    ! PRIVATE ENDPOINT !
    PERMITE AL USUARIO DESCONECTARSE DE LA APP, ESTE ENDPOINT SE ENCARGA
    DE AGREGAR A LA BLOCKLIST EL TOKEN DEL USUARIO QUE ESTÁ
    HACIENDO LA PETICIÓN.

    """

    add_jwt_to_blocklist(get_jwt())
    return JSONResponse(f"user <{role.user._email}> logged-out of current session").to_json()