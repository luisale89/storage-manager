from flask import Blueprint, abort

#extensions
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError
from flask_jwt_extended import get_jwt
from flask_jwt_extended import create_access_token
#models
from app.models.global_models import Plan
from app.models.main import Company, User, Role, RoleFunction
from app.utils.exceptions import APIException

#utils
from app.utils.helpers import ErrorMessages, JSONResponse
from app.utils.decorators import json_required, user_required
from app.utils.db_operations import handle_db_error, update_row_content
from app.utils.redis_service import add_jwt_to_blocklist
from app.utils.route_helper import valid_id
from app.utils.validations import validate_inputs, validate_string

#models
# from app.models.main import Company, User, Role

user_bp = Blueprint('user_bp', __name__)

#*1
@user_bp.route('/', methods=['GET'])
@json_required()
@user_required()
def get_user_profile(user):

    resp = JSONResponse(
        payload={
            "user": user.serialize_all()
        })

    return resp.to_json()

#*2
@user_bp.route('/', methods=['PUT'])
@json_required()
@user_required()
def update_user_profile(user, body):
    
    to_update = update_row_content(User, body)

    try:
        User.query.filter(User.id == user.id).update(to_update)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)
    
    resp = JSONResponse(message="user's profile has been updated")
    return resp.to_json()

#*3
@user_bp.route('/companies', methods=['GET'])
@json_required()
@user_required()
def get_user_roles(user):
    #returns all user's roles, giving information about the role_function and company.

    return JSONResponse(payload={
        "companies": list(map(lambda x: {**x.company.serialize(), "role": x.serialize_all()}, user.roles))
    }).to_json()


#*4
@user_bp.route('/companies', methods=['POST'])
@json_required({"company_name": str})
@user_required()
def change_active_role(user, body):
    #returns new jwt with target role in it, and block current jwt...

    owner = db.session.query(Role).join(Role.user).join(Role.role_function).filter(User.id==user.id, RoleFunction.code == 'owner').first()
    if owner is not None:
        raise APIException(f"user already has a company: <{owner.company.name}>", status_code=402)
        
    company_name = body['company_name']
    validate_inputs({
        "company_name": validate_string(company_name)
    })

    plan = Plan.query.filter(Plan.code == 'free').first()
    if plan is None:
        abort(500, "free plan does not exists in the database")

    role_function = db.session.query(RoleFunction).filter(RoleFunction.code == 'owner').first()
    if role_function is None:
        abort(500, "owner role does not exists in database")

    try:
        new_company = Company(
            name=company_name,
            address=body.get('address'),
            _plan_id=plan.id
        )

        new_role = Role(
            company = new_company,
            user = user,
            role_function = role_function,
            _isActive = True
        )
        db.session.add_all([new_company, new_role])
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse('new company created', status_code=201).to_json()


@user_bp.route('/companies/<int:company_id>/activate', methods=['GET'])
@json_required()
@user_required()
def activate_company_role(user, company_id=None):

    company_valid_id = valid_id(company_id)

    new_role = db.session.query(Role).join(Role.user).join(Role.company).filter(User.id==user.id, Company.id==company_valid_id).first()
    if new_role is None:
        raise APIException(ErrorMessages("company_id").notFound(), status_code=404)

    current_jwt = get_jwt()
    if new_role.id == current_jwt.get('role_id', None):
        raise APIException(f"company {company_valid_id} is already in use")

    #create new jwt with required role
    new_access_token = create_access_token(
        identity=user._email,
        additional_claims={
            'user_access_token': True,
            'role_access_token': True,
            'user_id': user.id,
            'role_id': new_role.id
        }
    )
    payload = {
        'user': user.serialize_all(),
        'role': new_role.serialize_all(),
        'company': new_role.company.serialize(),
        'access_token': new_access_token
    }
    add_jwt_to_blocklist(get_jwt()) #invalidates current jwt

    return JSONResponse("new company activated", payload=payload, status_code=201).to_json()


#*5
@user_bp.route('/logout', methods=['DELETE']) #logout user
@json_required()
@user_required()
def logout(user):
    """
    ! PRIVATE ENDPOINT !
    PERMITE AL USUARIO DESCONECTARSE DE LA APP, ESTE ENDPOINT SE ENCARGA
    DE AGREGAR A LA BLOCKLIST EL TOKEN DEL USUARIO QUE ESTÁ
    HACIENDO LA PETICIÓN.

    """

    add_jwt_to_blocklist(get_jwt())
    return JSONResponse(f"user <{user._email}> logged-out of current session").to_json()