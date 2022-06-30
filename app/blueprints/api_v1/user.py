from crypt import methods
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
from app.utils.route_decorators import json_required, user_required
from app.utils.db_operations import handle_db_error, update_row_content
from app.utils.redis_service import add_jwt_to_blocklist
from app.utils.validations import validate_string, validate_id


user_bp = Blueprint('user_bp', __name__)


@user_bp.route('/', methods=['GET'])
@json_required()
@user_required()
def get_user_profile(user):

    resp = JSONResponse(
        payload={
            "user": user.serialize_all()
        })

    return resp.to_json()


@user_bp.route('/', methods=['PUT'])
@json_required()
@user_required()
def update_user_profile(user, body):
    
    to_update, invalids, msg = update_row_content(User, body)
    if invalids:
        raise APIException.from_error(ErrorMessages(parameters=invalids, custom_msg=msg).bad_request)

    try:
        User.query.filter(User.id == user.id).update(to_update)
        db.session.commit()

    except SQLAlchemyError as e:
        handle_db_error(e)
    
    resp = JSONResponse(message="user's profile has been updated")
    return resp.to_json()


@user_bp.route('/companies', methods=['GET'])
@json_required()
@user_required()
def get_user_roles(user):
    #returns all user's roles, giving information about the role_function and company.

    return JSONResponse(payload={
        "companies": list(map(lambda x: {**x.company.serialize(), "role": x.serialize_all()}, user.roles))
    }).to_json()


@user_bp.route('/companies', methods=['POST'])
@json_required({"company_name": str})
@user_required()
def create_company(user, body):
    #create new company for current user...

    owned = user.get_owned_company()
    if owned is not None:
        raise APIException.from_error(
            ErrorMessages(
                parameters='user-company', 
                custom_msg=f"user is already owner of company: <{owned.company.name}>"
            ).conflict
        )
        
    company_name = body['company_name']

    valid, msg = validate_string(company_name)
    if not valid:
        raise APIException.from_error(ErrorMessages(parameters='company_name', custom_msg=msg).bad_request)

    plan = Plan.get_plan_by_code("free")
    if plan is None:
        abort(500, "free plan does not exists in the database")

    role_function = RoleFunction.get_rolefunc_by_code("owner")
    if role_function is None:
        abort(500, "owner role does not exists in database")

    try:
        new_company = Company(
            name=company_name,
            address=body.get('address', ''),
            plan=plan
        )

        new_role = Role(
            company = new_company,
            user = user,
            role_function = role_function
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

    company_valid_id = validate_id(company_id)

    new_role = db.session.query(Role).join(Role.user).join(Role.company).filter(User.id==user.id, Company.id==company_valid_id).first()
    if new_role is None:
        raise APIException.from_error(ErrorMessages(parameters='company_id').notFound)

    current_jwt = get_jwt()
    if new_role.id == current_jwt.get('role_id', None):
        raise APIException.from_error(ErrorMessages(parameters='company_id', custom_msg=f'[company]: {new_role.company.name} already in use').bad_request)

    #create new jwt with required role
    new_access_token = create_access_token(
        identity=user.email,
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
    success, redis_error = add_jwt_to_blocklist(get_jwt()) #invalidates current jwt
    if not success:
        raise APIException.from_error(ErrorMessages(parameters='blocklist', custom_msg=redis_error).service_unavailable)

    return JSONResponse("new company activated", payload=payload).to_json()


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

    success, redis_error = add_jwt_to_blocklist(get_jwt())
    if not success:
        raise APIException.from_error(ErrorMessages(parameters='blocklist', custom_msg=redis_error).service_unavailable)
        
    return JSONResponse(f"user <{user.email}> logged-out of current session").to_json()


@user_bp.route("/order-requests", methods=["GET"])
@json_required()
@user_required()
def get_user_orders(user):

    return JSONResponse(message="in development...", status_code=200).to_json()


@user_bp.route("/order-requests", methods=["POST"])
@json_required()
@user_required()
def create_order_request(user, body):

    return JSONResponse(message="in development...").to_json()


@user_bp.route("/order-requests/<int:orq_id>", methods=["PUT"])
@json_required()
@user_required()
def update_order_request(user, body, orq_id):

    return JSONResponse(message="in development...").to_json()


@user_bp.route("/order-requests/<int:orq_id>", methods=["DELETE"])
@json_required()
@user_required()
def delete_order_request(user, orq_id):

    return JSONResponse("in development...").to_json()


@user_bp.route("/order-requests/<int:orq_id>/items", methods=["POST"])
@json_required()
@user_required()
def add_item_to_order(user, body, orq_id):

    return JSONResponse("in development...").to_json()


@user_bp.route("/order-requests/items/<int:item_id>", methods=["PUT"])
@json_required()
@user_required()
def update_item_in_order(user, body, item_id):

    return JSONResponse("in development...").to_json()


@user_bp.route("/order-requests/items/<int:item_id>", methods=["DELETE"])
@json_required()
@user_required()
def delete_item_in_order(user, item_id):

    return JSONResponse("in development...").to_json()