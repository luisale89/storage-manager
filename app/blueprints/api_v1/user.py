from flask import Blueprint

#extensions
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError

#models
from app.models.main import User, Company

#utils
from app.utils.helpers import JSONResponse
from app.utils.decorators import json_required, user_required
from app.utils.db_operations import handle_db_error, update_row_content

#models
# from app.models.main import Company, User, Role

user_bp = Blueprint('user_bp', __name__)


@user_bp.route('/', methods=['GET'])
@json_required()
@user_required()
def get_user(user):
    """
    * PRIVATE ENDPOINT *
    Obtiene los datos de perfil de un usuario.
    requerido: {} # header of the request includes JWT wich is linked to the user email
    """

    resp = JSONResponse(
        message="user's profile", 
        payload={
            "user": user.serialize(detail=True)
        })

    return resp.to_json()


@user_bp.route('/update', methods=['PUT'])
@json_required()
@user_required()
def update_user(user, body):
    
    to_update = update_row_content(User, body)

    try:
        User.query.filter(User.id == user.id).update(to_update)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)
    
    resp = JSONResponse(message="user's profile has been updated")
    return resp.to_json()


@user_bp.route('/company', methods=['GET'])
@json_required()
@user_required(with_company=True)
def get_user_company(user):

    resp = JSONResponse(message=f"company owned by <{user.fname}>", payload={
        "company": user.company.serialize(detail=True)
    })
    return resp.to_json()


@user_bp.route('/company/update', methods=['PUT'])
@json_required()
@user_required()
def update_user_company(user, body):

    currencies = body.get('currencies', None)
    if currencies is not None and isinstance(currencies, list):
        body['currencies'] = {"all": currencies}

    to_update = update_row_content(Company, body)

    try:
        Company.query.filter(Company._user_id == user.id).update(to_update)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f'Company updated').to_json()