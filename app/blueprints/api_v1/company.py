from crypt import methods
from flask import Blueprint, request
from app.models.global_models import RoleFunction

#extensions
from app.models.main import Company, Role
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import ErrorMessages, JSONResponse, str_to_int
from app.utils.route_helper import get_pagination_params, pagination_form
from app.utils.decorators import json_required, user_required
from app.utils.db_operations import handle_db_error, update_row_content, ValidRelations


company_bp = Blueprint('company_bp', __name__)


@company_bp.route('/', methods=['GET'])
@json_required()
@user_required()
def get_user_company(role):

    resp = JSONResponse(payload={
        "company": role.company.serialize_all()
    })
    return resp.to_json()


@company_bp.route('/', methods=['PUT'])
@json_required()
@user_required(level=0) #owner only
def update_company(role, body):

    currencies = body.get('currencies', None)
    if currencies is not None and isinstance(currencies, list):
        body['currencies'] = {"all": currencies}

    to_update = update_row_content(Company, body)

    try:
        Company.query.filter(Company.id == role.company.id).update(to_update)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f'Company updated').to_json()


@company_bp.route('/users', methods=['GET'])
@json_required()
@user_required()#any user
def get_company_users(role):

    return JSONResponse(payload={
        "users": list(map(lambda x: {**x.user.serialize(), "role": x.serialize_all()}, role.company.roles))
    }).to_json()

@company_bp.route('/users', methods=['POST'])
@json_required()
@user_required(level=1)
def invite_user(role, body):

    return JSONResponse("in development...")


@company_bp.route('/users/<int:user_id>', methods=['GET'])
@json_required()
@user_required(level=1)
def get_company_user_info(role, user_id=None):

    return JSONResponse("in development...")


@company_bp.route('/users/<int:user_id>', methods=['PUT'])
@json_required()
@user_required(level=1)
def update_user_company_relation(role, body, user_id=None):

    return JSONResponse("in development...")


@company_bp.route('/users/<int:user_id>', methods=['DELETE'])
@json_required()
@user_required(level=1)
def delete_user_company_relation(role, user_id=None):

    return JSONResponse("in development...")


@company_bp.route('/roles', methods=['GET'])
@json_required()
@user_required()#any user
def get_company_roles(role):

    return JSONResponse(payload={
        "roles": list(map(lambda x: x.serialize(), db.session.query(RoleFunction).all()))
    }).to_json()