from crypt import methods
from flask import Blueprint, current_app, request
from app.models.global_models import RoleFunction

#extensions
from app.models.main import Company, User, Role
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import ErrorMessages, JSONResponse, random_password, str_to_int
from app.utils.route_helper import get_pagination_params, pagination_form
from app.utils.decorators import json_required, user_required
from app.utils.db_operations import get_user_by_email, handle_db_error, update_row_content, ValidRelations
from app.utils.validations import validate_email, validate_inputs
from app.utils.email_service import invite_new_user


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

    to_update = update_row_content(Company, body)

    try:
        Company.query.filter(Company.id == role.company.id).update(to_update)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f'Company updated').to_json()


@company_bp.route('/users', methods=['GET'])
@json_required()
@user_required(level=1)#andmin user
def get_company_users(role):

    return JSONResponse(payload={
        "users": list(map(lambda x: {**x.user.serialize(), "role": x.serialize_all()}, role.company.roles))
    }).to_json()


@company_bp.route('/users', methods=['POST'])
@json_required({"email": str, "role_id": int})
@user_required(level=1)
def invite_user(role, body):

    email = body['email']
    validate_inputs({
        'email': validate_email(email)
    })
    role_id = body['role_id']

    new_role_function = db.session.query(RoleFunction).get(role_id)
    if new_role_function is None:
        current_app.logger.info(f"role-not-found: <q.role: {role_id}>")
        raise APIException(f'{ErrorMessages("role_id").notFound()}')

    if role.role_function.level > new_role_function.level:
        raise APIException(f'user out of reach', status_code=406)

    user = get_user_by_email(email, silent=True)
    #nuevo usuario...
    if user is None:
        invite_new_user(user_email=email, company_name=role.company.name)

        try:
            new_user = User(
                _email=email,
                password = random_password(),
                _email_confirmed=False,
                _signup_completed=False,
            )
            new_role = Role(
                user = new_user,
                _company_id = role._company_id,
                role_function = new_role_function
            )
            db.session.add_all([new_user, new_role])
            db.session.commit()
        except SQLAlchemyError as e:
            handle_db_error(e)

        return JSONResponse("new user invited", status_code=201).to_json()

    #ususario existente...
    rel = db.session.query(User).join(User.roles).join(Role.company).\
        filter(User.id == user.id, Company.id == role._company_id).first()
    
    if rel is not None:
        raise APIException(f'User <{email}> is already listed in current company', status_code=409)
    
    invite_new_user(user_email=email, company_name=role.company.name, user_name=user.name)
    try:
        new_role = Role(
            _company_id = role._company_id,
            user = user,
            role_function = new_role_function
        )
        db.session.add(new_role)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse('existing user invited').to_json()


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


# @company_bp.route('/categories', methods=['GET'])
# @company_bp.route('/categories/<int:category_id>')