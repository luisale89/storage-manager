from flask import Blueprint, request, current_app
from flask_jwt_extended import get_jwt_identity

#extensions
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError

#models
from app.models.main import User

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import normalize_names, JSONResponse, ErrorMessages
from app.utils.validations import validate_inputs, only_letters
from app.utils.decorators import json_required, user_required
from app.utils.db_operations import get_user_by_email, update_row_content

#models
# from app.models.main import Company, User, Role

user_bp = Blueprint('user_bp', __name__)


@user_bp.route('/', methods=['GET'])
@json_required()
@user_required()
def get_user():
    """
    * PRIVATE ENDPOINT *
    Obtiene los datos de perfil de un usuario.
    requerido: {} # header of the request includes JWT wich is linked to the user email
    """
    identity = get_jwt_identity()
    # user = get_user_by_email(identity) #get_jwt_indentity get the user id from jwt.
    user = get_user_by_email(email=identity)
    if user is None:
        raise APIException(f"email: {identity} not found in database", status_code=404, app_result="q_not_found")

    resp = JSONResponse(
        message="user's profile", 
        payload={
            "user": {**user.serialize(), **user.serialize_private()}
        })

    return resp.to_json()


@user_bp.route('/update', methods=['PUT'])
@json_required()
@user_required()
def update_user():

    user = get_user_by_email(get_jwt_identity()) #jwt identity = user_email
    body = request.get_json(silent=True)
    
    to_update = update_row_content(user, body)

    try:
        User.query.filter(User.id == user.id).update(to_update)
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(e) #log error
        raise APIException(ErrorMessages().dbError, status_code=500)
    
    resp = JSONResponse(message="user's profile has been updated", payload={"user": user.serialize()})
    return resp.to_json()


@user_bp.route('/company', methods=['GET'])
@json_required()
@user_required()
def get_user_companies():

    user = get_user_by_email(get_jwt_identity())

    resp = JSONResponse(message=f"company owned by <{user.fname}>", payload={
        "company": user.company.serialize() if user.company is not None else {}
    })
    return resp.to_json()