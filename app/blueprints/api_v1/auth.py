from random import randint
from flask import Blueprint
#extensions
from app.extensions import db
from app.models.global_models import RoleFunction
#models
from app.models.main import (
    User, Company, Plan, Role
)
#exceptions
from sqlalchemy.exc import SQLAlchemyError
from app.utils.exceptions import APIException
#jwt
from werkzeug.security import check_password_hash
from flask_jwt_extended import create_access_token
#utils
from app.utils.helpers import (
    normalize_string, JSONResponse
)
from app.utils.validations import (
    validate_email, validate_pw, validate_inputs, validate_string
)
from app.utils.email_service import send_verification_email
from app.utils.decorators import (
    json_required, verification_token_required, verified_token_required
)
from app.utils.redis_service import add_jwt_to_blocklist
from app.utils.db_operations import ValidRelations, get_user_by_email, handle_db_error


auth_bp = Blueprint('auth_bp', __name__)


@auth_bp.route('/email/<string:email>', methods=['GET'])
@json_required()
def check_email(email):

    validate_inputs({
        'email': validate_email(email)
    })
    user = get_user_by_email(email) #raises 404 if user is not found in db
    
    return JSONResponse(
        payload={
            'companies': list(map(lambda x: {'name': x.company.name, 'id': x.company.id}, user.roles)),
            'status': user._status, 
            'email-confirmed': user._email_confirmed
        }
    ).to_json()


@auth_bp.route('/sign-up', methods=['POST']) #normal signup
@json_required({"password":str, "fname":str, "lname":str, "company_name": str})
@verified_token_required()
def signup(body, claims): #from decorators functions
    """
    * PUBLIC ENDPOINT *
    Crea un nuevo usuario para la aplicación
    """
    email = claims.get('sub') #email is the jwt id in verified token 
    password, fname, lname, company_name = body['password'], body['fname'], body['lname'], body['company_name']
    validate_inputs({
        'password': validate_pw(password),
        'fname': validate_string(fname),
        'lname': validate_string(lname),
        'company_name': validate_string(company_name)
    })

    
    if User.check_if_user_exists(email=email):
        add_jwt_to_blocklist(claims) #bloquea verified jwt
        raise APIException(f"User {email} already exists in database", status_code=409)

    plan = Plan.query.filter(Plan.code == 'free').first()
    if plan is None:
        raise APIException(f"free plan does not exists in database", status_code=500)

    role_function = db.session.query(RoleFunction).filter(RoleFunction.code == 'owner').first()
    if role_function is None:
        raise APIException(f"owner role does not exists", status_code=500)

    #?processing
    try:
        new_user = User(
            _email=email, 
            _email_confirmed=True,
            _status='active',
            password=password, 
            fname=normalize_string(fname, spaces=True),
            lname=normalize_string(lname, spaces=True)
        )
        
        new_company = Company(
            name = normalize_string(company_name, spaces=True),
            address = body.get("address", {}),
            _plan_id = plan.id
        )

        new_role = Role(
            company = new_company,
            user = new_user,
            role_function = role_function
        )

        db.session.add_all([new_user, new_company, new_role])
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    add_jwt_to_blocklist(claims) #bloquea verified-jwt 

    return JSONResponse(
        message="new user has been created"
    ).to_json()


@auth_bp.route('/login', methods=['POST']) #normal login
@json_required({"email":str, "password":str, "company": int})
def login(body): #body from json_required decorator
    """
    * PUBLIC ENDPOINT *
    requerido: {
        "email": email, <str>
        "password": password, <str>
    }
    """
    email, pw, company_id = body['email'].lower(), body['password'], body['company']

    validate_inputs({
        'email': validate_email(email),
        'password': validate_pw(pw)
    })

    #?processing
    user = get_user_by_email(email)

    if user._status is None or user._status != 'active':
        raise APIException("user is not active", status_code=402)

    if not user._email_confirmed:
        raise APIException("user's email not validated", status_code=401)

    if not check_password_hash(user._password_hash, pw):
        raise APIException("wrong password", status_code=403)
    
    role = ValidRelations().user_company(user.id, company_id)

    #*user-access-token
    access_token = create_access_token(
        identity=email, 
        additional_claims={
            'user_access_token': True,
            'role_id': role.id
        }
    )

    #?response
    return JSONResponse(
        message="user logged in",
        payload={
            "user": user.serialize_all(),
            "company": role.company.serialize_all(),
            "role": role.role_function.serialize(),
            "access_token": access_token
        }
    ).to_json()


@auth_bp.route('/validation/<string:email>', methods=['GET'])
@json_required()
def get_verification_code(email):
    """
    * PUBLIC ENDPOINT *
    Endpoint to request a new verification code to validate that email really exists
    """

    validate_inputs({
        'email': validate_email(email)
    })

    normalized_email = email.lower()

    #response
    random_code = randint(100000, 999999)
    token = create_access_token(
        identity=normalized_email, 
        additional_claims={
            'verification_code': random_code,
            'verification_token': True
        }
    )

    send_verification_email(verification_code=random_code, user={'email': normalized_email}) #503 error raised in funct definition

    return JSONResponse(
        message='verification code sent to user', 
        payload={
            'user_email': normalized_email,
            'verification_token': token
    }).to_json()


@auth_bp.route('/validation', methods=['PUT'])
@json_required({'code':int})
@verification_token_required()
def check_verification_code(body, claims):
    """
    ! PRIVATE ENDPOINT !
    endpoint: /check-verification-code
    methods: [PUT]
    description: endpoint to validate user's verification code sent to them by email.

    """
    code_in_request = body.get('code')
    code_in_token = claims.get('verification_code')

    if (code_in_request != code_in_token):
        raise APIException("invalid verification code")
    
    add_jwt_to_blocklist(claims) #invalida el uso del token una vez se haya validado del codigo

    verified_user_token = create_access_token(
        identity=claims['sub'], 
        additional_claims={
            'verified_token': True
        }
    )

    return JSONResponse(
        "code verification success", 
        payload={
            'verified_token': verified_user_token,
            'user_email': claims['sub']
        }
    ).to_json()


@auth_bp.route("/email/validate", methods=['GET'])
@json_required()
@verified_token_required()
def confirm_user_email(claims):
    """
    ! PRIVATE ENDPOINT !
    endpoint: /confirm-user-email
    methods: [PUT]
    description: endpoint to confirm user email, verified_token required..

    """
    user = get_user_by_email(claims['sub'])
    user._email_confirmed = True

    try:
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)
    
    add_jwt_to_blocklist(claims)

    return JSONResponse(message="user's email has been validated").to_json()


@auth_bp.route("/password", methods=['PUT'])
@json_required({"password":str})
@verified_token_required()
def password_change(body, claims):
    """
    URL: /password-change
    methods: [PUT]
    description: endpoint to change user's password.

    """
    new_password = body.get('password')

    validate_inputs({
        'password': validate_pw(new_password)
    })

    user = get_user_by_email(claims['sub'])
    user.password = new_password

    try:
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    add_jwt_to_blocklist(claims)

    return JSONResponse(message="user's password has been updated").to_json()


@auth_bp.route('/login/superuser', methods=['POST']) #super-user login
@json_required({"password":str})
@verified_token_required()
def login_super_user(body, claims):
    """
    * VERIFIED TOKEN ONLY *
    requerido: {
        "password": password, <str>
    }
    """
    pw = body['password']

    validate_inputs({
        'password': validate_pw(pw)
    })

    email = claims['sub']
    user = get_user_by_email(email)

    if email != 'luis.lucena89@gmail.com': #? debug - se debe agregar una condicion valida para produccion..
        raise APIException("unauthorized user", status_code=401, app_result='error')

    #?processing

    if user._status is None or user._status != 'active':
        raise APIException("user is not active", status_code=402)

    if not user._email_confirmed:
        raise APIException("user's email not validated", status_code=401)

    if not check_password_hash(user._password_hash, pw):
        raise APIException("wrong password", status_code=403)
    
    #*super-user_access-token
    access_token = create_access_token(
        identity=email, 
        additional_claims={
            'user_access_token': True,
            'super_user': True,
            'user_id': user.id
        }
    )

    add_jwt_to_blocklist(claims)

    #?response
    return JSONResponse(
        message="super user logged in",
        payload={
            "user_email": email,
            "su_access_token": access_token
        },
        status_code=200
    ).to_json()