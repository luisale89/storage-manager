

from random import randint
from flask import (
    Blueprint, request, current_app
)
#extensions
from app.extensions import (
    db
)
#models
from app.models.main import (
    User, Company, Plan
)
#exceptions
from sqlalchemy.exc import SQLAlchemyError
from app.utils.exceptions import APIException
#jwt
from werkzeug.security import check_password_hash
from flask_jwt_extended import (
    create_access_token, get_jwt
)
#utils
from app.utils.helpers import (
    normalize_string, JSONResponse, ErrorMessages
)
from app.utils.validations import (
    validate_email, validate_pw, validate_inputs, validate_string
)
from app.utils.email_service import (
    send_verification_email
)
from app.utils.decorators import (
    json_required, verification_token_required, verified_token_required, user_required
)
from app.utils.redis_service import add_jwt_to_blocklist
from app.utils.db_operations import get_user_by_email


auth_bp = Blueprint('auth_bp', __name__)


@auth_bp.route('check-email/<string:email>', methods=['GET'])
@json_required()
def check_email(email):
    
    resp = JSONResponse(
        message="ok",
        payload={
            "exists": User.check_if_user_exists(email.lower())
        }
    )
    return resp.to_json()


@auth_bp.route('/sign-up', methods=['POST']) #normal signup
@json_required({"password":str, "fname":str, "lname":str, "company_name": str, "company_code": str})
@verified_token_required()
def signup():
    """
    * PUBLIC ENDPOINT *
    Crea un nuevo usuario para la aplicación
    requerido: {
        "password": str,
        "fname": str,
        "lname": str
    }
    """
    claims = get_jwt()
    email = claims.get('sub') #email is the jwt id for verified token 
    body = request.get_json(silent=True)
    password, fname, lname, company_name, company_code = body['password'], body['fname'], body['lname'], body['company_name'], body['company_code']
    validate_inputs({
        'password': validate_pw(password),
        'fname': validate_string(fname),
        'lname': validate_string(lname),
        'company_name': validate_string(company_name),
        'company_code': validate_string(company_code)
    })

    q_user = User.check_if_user_exists(email=email)
    plan_id = body.get('plan_id', 1)
    plan = Plan.query.filter(Plan.id == plan_id).first()

    if plan is None:
        raise APIException(f"plan id: {plan_id} does not exists")

    if q_user:
        add_jwt_to_blocklist(claims) #bloquea jwt 
        raise APIException(f"User {email} already exists in database", status_code=409)

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
            code = normalize_string(company_code),
            address = body.get("address", {}),
            _plan_id = 1, #debug only -- ned to fix this
            user = new_user
        )

        db.session.add(new_user)
        db.session.add(new_company)
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(e) #log error
        raise APIException(ErrorMessages().dbError, status_code=500)

    add_jwt_to_blocklist(claims) #bloquea jwt 

    resp = JSONResponse(
        message="new user has been created"
    )
    #?response
    return resp.to_json()


@auth_bp.route('/login', methods=['POST']) #normal login
@json_required({"email":str, "password":str})
def login():
    """
    * PUBLIC ENDPOINT *
    requerido: {
        "email": email, <str>
        "password": password, <str>
    }
    """
    body = request.get_json(silent=True)
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
    resp = JSONResponse(
        message="user logged in",
        payload={
            "user": user.serialize(),
            "company": user.serialize_company(),
            "access_token": access_token
        }
    )

    return resp.to_json()


@auth_bp.route('/logout', methods=['DELETE']) #logout user
@json_required()
@user_required()
def logout():
    """
    ! PRIVATE ENDPOINT !
    PERMITE AL USUARIO DESCONECTARSE DE LA APP, ESTE ENDPOINT SE ENCARGA
    DE AGREGAR A LA BLOCKLIST EL TOKEN DEL USUARIO QUE ESTÁ
    HACIENDO LA PETICIÓN.

    """

    add_jwt_to_blocklist(get_jwt())
    resp = JSONResponse("user logged-out of current session")
    return resp.to_json()


@auth_bp.route('/get-verification-code/<email>', methods=['GET'])
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

    response = JSONResponse(
        message='verification code sent to user', 
        payload={
            'user_email': normalized_email,
            'verification_token': token
    })

    return response.to_json()


@auth_bp.route('/check-verification-code', methods=['PUT'])
@json_required({'verification_code':int})
@verification_token_required()
def check_verification_code():
    """
    ! PRIVATE ENDPOINT !
    endpoint: /check-verification-code
    methods: [PUT]
    description: endpoint to validate user's verification code sent to them by email.

    """
    # body = request.get_json(silent=True)
    # claims = get_jwt()
    claims = get_jwt()
    code_in_request = request.get_json().get('verification_code')
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


    resp = JSONResponse(
        "code verification success", 
        payload={
            'verified_token': verified_user_token,
            'user_email': claims['sub']
        }
    )
    
    return resp.to_json()


@auth_bp.route("/confirm-user-email", methods=['GET'])
@json_required()
@verified_token_required()
def confirm_user_email():
    """
    ! PRIVATE ENDPOINT !
    endpoint: /confirm-user-email
    methods: [PUT]
    description: endpoint to confirm user email, verified_token required..

    """
    claims = get_jwt()
    user = get_user_by_email(claims['sub'])

    user._email_confirmed = True

    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(e)
        raise APIException(ErrorMessages().dbError, status_code=500) 
    
    add_jwt_to_blocklist(claims)

    resp = JSONResponse(message="user's email has been confirmed")
    return resp.to_json()


@auth_bp.route("/password-change", methods=['PUT'])
@json_required({"new_password":str})
@verified_token_required()
def password_change():
    """
    URL: /password-change
    methods: [PUT]
    description: endpoint to change user's password.

    """
    claims = get_jwt()
    new_password = request.get_json().get('new_password')

    validate_inputs({
        'password': validate_pw(new_password)
    })

    user = get_user_by_email(claims['sub'])
    
    user.password = new_password

    try:
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(e)
        raise APIException(ErrorMessages().dbError, status_code=500)

    add_jwt_to_blocklist(claims)

    return JSONResponse(message="user's password has been updated").to_json()


@auth_bp.route('/login/super-user', methods=['POST']) #super-user login
@json_required({"password":str})
@verified_token_required()
def login_super_user():
    """
    * VERIFIED TOKEN ONLY *
    requerido: {
        "password": password, <str>
    }
    """
    body = request.get_json(silent=True)
    pw = body['password']

    validate_inputs({
        'password': validate_pw(pw)
    })

    claims = get_jwt()
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
    resp = JSONResponse(
        message="super user logged in",
        payload={
            "user_email": email,
            "su_access_token": access_token
        },
        status_code=200
    )

    return resp.to_json()