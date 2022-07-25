from flask import Blueprint, abort

#extensions
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func
from flask_jwt_extended import get_jwt
from flask_jwt_extended import create_access_token
#models
from app.models.global_models import Plan
from app.models.main import Company, User, Role, RoleFunction
from app.utils.exceptions import APIException

#utils
from app.utils.helpers import ErrorMessages as EM, JSONResponse, StringHelpers, IntegerHelpers
from app.utils.route_decorators import json_required, user_required
from app.utils.db_operations import handle_db_error, update_row_content, Unaccent
from app.utils.redis_service import RedisClient


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
    
    to_update, invalids = update_row_content(User, body)
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

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
        "companies": list(map(lambda x: {**x.company.serialize(), **x.serialize_all()}, user.roles))
    }).to_json()


@user_bp.route('/companies', methods=['POST'])
@json_required({"company_name": str})
@user_required()
def create_company(user, body):
    #create new company for current user...

    owned = user.roles.join(Role.role_function).filter(RoleFunction.code == 'owner').first()
    if owned:
        raise APIException.from_error(EM({"user_company": "user is already owner of company"}).conflict)
        
    company_name = StringHelpers(body["company_name"])
    valid, msg = company_name.is_valid_string()
    if not valid:
        raise APIException.from_error(EM({"company_name": msg}).bad_request)

    name_exists = db.session.query(Company).\
        filter(Unaccent(func.lower(Company.name)) == company_name.no_accents.lower()).first()
    if name_exists:
        raise APIException.from_error(EM({"company_name": f"name [{company_name}] already exists"}).conflict)

    plan = Plan.get_plan_by_code("free")
    if plan is None:
        abort(500, "free plan does not exists in the database")

    role_function = RoleFunction.get_rolefunc_by_code("owner")
    if role_function is None:
        abort(500, "owner role does not exists in database")

    try:
        new_company = Company(
            name=company_name.value,
            plan=plan
        )

        new_role = Role(
            company = new_company,
            user = user,
            role_function = role_function,
            inv_accepted = True
        )
        db.session.add_all([new_company, new_role])
        db.session.commit()

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse('new company created', status_code=201).to_json()


@user_bp.route('/companies/<int:company_id>/accept', methods=["GET"])
@json_required()
@user_required()
def accept_company_invitation(user, company_id):

    valid, msg = IntegerHelpers.is_valid_id(company_id)
    if not valid:
        raise APIException.from_error(EM({"company_id": msg}).bad_request)

    target_role = db.session.query(Role).join(Role.user).join(Role.company).\
        filter(User.id == user.id, Company.id == company_id).first()

    if not target_role:
        raise APIException.from_error(EM({"company_id": f"ID-{company_id} not found"}))

    if not target_role.is_active:
        raise APIException.from_error(EM({"role": "role has been disabled"}).user_not_active)

    try:
        target_role.inv_accepted = True
        db.session.commit()
    
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message="invitation accepted",
    ).to_json()


@user_bp.route('/companies/<int:company_id>/activate', methods=['GET'])
@json_required()
@user_required()
def activate_company_role(user, company_id=None):

    valid, msg = IntegerHelpers.is_valid_id(company_id)
    if not valid:
        raise APIException.from_error(EM({"company_id": msg}).bad_request)

    new_role = db.session.query(Role).join(Role.user).join(Role.company).\
        filter(User.id==user.id, Company.id==company_id).first()
    if new_role is None:
        raise APIException.from_error(EM({"company_id": f"value not found"}).notFound)

    if not new_role.inv_accepted:
        raise APIException.from_error(EM({"role": "invitation is not accepted"}).bad_request)
    
    if not new_role.is_active:
        raise APIException.from_error(EM({"role": "role has been disabled"}).user_not_active)

    current_jwt = get_jwt()
    if new_role.id == current_jwt.get('role_id', None):
        raise APIException.from_error(EM({"role_id": f"company [{new_role.company.name}] already activated"}).conflict)

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
    success, redis_error = RedisClient().add_jwt_to_blocklist(get_jwt()) #invalidates current jwt
    if not success:
        raise APIException.from_error(EM(redis_error).service_unavailable)

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

    success, redis_error = RedisClient().add_jwt_to_blocklist(get_jwt())
    if not success:
        raise APIException.from_error(EM(redis_error).service_unavailable)
        
    return JSONResponse(f"user <{user.email}> logged-out of current session").to_json()


@user_bp.route("/order-requests", methods=["GET"])
@json_required()
@user_required()
def get_user_orders(user):

    return JSONResponse(message="in development...", status_code=200).to_json()


@user_bp.route("/order-requests", methods=["POST"])
@json_required()
@user_required(customer=True)
def create_order_request(user, company, body):

    return JSONResponse(message=f"in development... hi: {user.fname} - purchasing in {company.name}").to_json()


@user_bp.route("/order-requests/<int:orq_id>", methods=["PUT"])
@json_required()
@user_required(customer=True)
def update_order_request(user, company, body, orq_id):

    return JSONResponse(message="in development...").to_json()


@user_bp.route("/order-requests/<int:orq_id>", methods=["DELETE"])
@json_required()
@user_required(customer=True)
def delete_order_request(user, company, orq_id):

    return JSONResponse("in development...").to_json()


@user_bp.route("/order-requests/<int:orq_id>/items", methods=["POST"])
@json_required()
@user_required(customer=True)
def add_item_to_order(user, company, body, orq_id):

    return JSONResponse("in development...").to_json()


@user_bp.route("/order-requests/items/<int:item_id>", methods=["PUT"])
@json_required()
@user_required(customer=True)
def update_item_in_order(user, company, body, item_id):

    return JSONResponse("in development...").to_json()


@user_bp.route("/order-requests/items/<int:item_id>", methods=["DELETE"])
@json_required()
@user_required(customer=True)
def delete_item_in_order(user, company, item_id):

    return JSONResponse("in development...").to_json()