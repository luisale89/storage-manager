from flask import Blueprint
from app.models.global_models import RoleFunction

#extensions
from app.models.main import Company, User, Role
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import ErrorMessages, JSONResponse, random_password
from app.utils.decorators import json_required, role_required
from app.utils.db_operations import handle_db_error, update_row_content
from app.utils.validations import validate_email, validate_inputs, validate_id
from app.utils.email_service import send_user_invitation


company_bp = Blueprint('company_bp', __name__)

#*1
@company_bp.route('/', methods=['GET'])
@json_required()
@role_required()
def get_user_company(role):

    resp = JSONResponse(payload={
        "company": role.company.serialize_all()
    })
    return resp.to_json()

#*2
@company_bp.route('/', methods=['PUT'])
@json_required()
@role_required(level=0) #owner only
def update_company(role, body):

    to_update = update_row_content(Company, body)

    try:
        Company.query.filter(Company.id == role.company.id).update(to_update)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f'Company updated').to_json()

#*3
@company_bp.route('/users', methods=['GET'])
@json_required()
@role_required(level=1)#andmin user
def get_company_users(role):

    roles = db.session.query(Role).join(Role.user).filter(Role._company_id == role._company_id).order_by(func.lower(User.fname).asc()).all()
    return JSONResponse(payload={
        "users": list(map(lambda x: {**x.user.serialize(), "role": x.serialize_all()}, roles))
    }).to_json()

#*4
@company_bp.route('/users', methods=['POST'])
@json_required({"email": str, "role_id": int})
@role_required(level=1)
def invite_user(role, body):

    email = body['email'].lower()
    validate_inputs({
        'email': validate_email(email)
    })
    new_role_function = RoleFunction.get_rolefunc_by_id(body['role_id'])
    if new_role_function is None:
        raise APIException.from_error(ErrorMessages("role_id").notFound)

    if role.role_function.level > new_role_function.level:
        raise APIException.from_error(ErrorMessages("role_level").unauthorized)

    user = User.get_user_by_email(email)
    #nuevo usuario...
    if user is None:

        send_user_invitation(user_email=email, company_name=role.company.name)
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
        raise APIException.from_error(
            ErrorMessages('email', custom_msg=f'User <{email}> is already listed in current company').conflict
        )
    
    send_user_invitation(user_email=email, company_name=role.company.name, user_name=user.fname)
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

#*5
@company_bp.route('/users/<int:user_id>', methods=['PUT'])
@json_required({'role_id':int, 'is_active':bool})
@role_required(level=1)
def update_user_company_relation(role, body, user_id=None):

    role_id = body['role_id']
    new_status = body['is_active']
    error = ErrorMessages()

    target_role = Role.relation_user_company(user_id, role.company.id)
    if target_role is None:
        error.parameters.append('user_id')
    
    new_rolefunction = RoleFunction.get_rolefunc_by_id(role_id)
    if new_rolefunction is None:
        error.parameters.append('role_id')

    if error.parameters != []:
        raise APIException.from_error(error.notFound)

    if role.role_function.level > new_rolefunction.level:
        raise APIException.from_error(ErrorMessages("role_level").unauthorized)
        
    try:
        target_role.role_function = new_rolefunction
        target_role._isActive = new_status
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse("user role updated").to_json()

#*6
@company_bp.route('/users/<int:user_id>', methods=['DELETE'])
@json_required()
@role_required(level=1)
def delete_user_company_relation(role, user_id=None):

    target_role = Role.relation_user_company(user_id, role.company.id)
    if target_role is None:
        raise APIException.from_error(ErrorMessages('user_id').notFound)
    try:
        db.session.delete(target_role)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse("user relation deleted").to_json()

#*7
@company_bp.route('/roles/', methods=['GET'])
@json_required()
@role_required()#any user
def get_company_roles(role):

    return JSONResponse(payload={
        "roles": list(map(lambda x: x.serialize(), db.session.query(RoleFunction).all()))
    }).to_json()