from random import randint
from flask import Blueprint
#extensions
from app.extensions import db
#models
from app.models.main import (
    User, Company, Plan
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
from app.utils.db_operations import get_user_by_email, handle_db_error


auth_bp = Blueprint('auth_bp', __name__)


@auth_bp.route('/email/<string:email>', methods=['GET'])
@json_required()
def check_email(email):

    validate_inputs({
        'email': validate_email(email)
    })
    
    return JSONResponse(
        message="ok",
        payload={
            "exists": User.check_if_user_exists(email.lower())
        }
    ).to_json()


@auth_bp.route('/sign-up', methods=['POST']) #normal signup
@json_required({"password":str, "fname":str, "lname":str, "company_name": str})
@verified_token_required()
def signup(body, claims): #from decorators functions
    """
    * PUBLIC ENDPOINT *
    Crea un nuevo usuario para la aplicación
    requerido: {
        "password": str,
        "fname": str,
        "lname": str,
        "company_name": str,
    }
    """
    email = claims.get('sub') #email is the jwt id in verified token 
    password, fname, lname, company_name = body['password'], body['fname'], body['lname'], body['company_name']
    validate_inputs({
        'password': validate_pw(password),
        'fname': validate_string(fname),
        'lname': validate_string(lname),
        'company_name': validate_string(company_name)
    })

    q_user = User.check_if_user_exists(email=email)
    if q_user:
        add_jwt_to_blocklist(claims) #bloquea verified jwt
        raise APIException(f"User {email} already exists in database", status_code=409)

    plan_id = body.get('plan_id', 1)
    plan = Plan.query.filter(Plan.id == plan_id).first()

    if plan is None:
        raise APIException(f"plan id: {plan_id} does not exists")

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
            _plan_id = 1, #debug only -- ned to fix this
            user = new_user
        )

        db.session.add(new_user)
        db.session.add(new_company)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    add_jwt_to_blocklist(claims) #bloquea verified-jwt 

    return JSONResponse(
        message="new user has been created"
    ).to_json()


@auth_bp.route('/login', methods=['POST']) #normal login
@json_required({"email":str, "password":str})
def login(body): #body from json_required decorator
    """
    * PUBLIC ENDPOINT *
    requerido: {
        "email": email, <str>
        "password": password, <str>
    }
    """
    email, pw = body['email'].lower(), body['password']

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
    
    #*user-access-token
    access_token = create_access_token(
        identity=email, 
        additional_claims={
            'user_access_token': True,
            'user_id': user.id
        }
    )

    #?response
    return JSONResponse(
        message="user logged in",
        payload={
            "user": user.serialize_all(),
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