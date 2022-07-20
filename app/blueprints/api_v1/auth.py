from random import randint
from flask import Blueprint, request
# extensions
from app.extensions import db
# models
from app.models.main import (
    User, Company, Role
)
# exceptions
from sqlalchemy.exc import SQLAlchemyError
from app.utils.exceptions import APIException
# jwt
from werkzeug.security import check_password_hash
from flask_jwt_extended import create_access_token
# utils
from app.utils.helpers import (
    ErrorMessages as EM, IntegerHelpers, JSONResponse, QueryParams, StringHelpers
)
from app.utils.email_service import send_verification_email
from app.utils.route_decorators import (
    json_required, verification_token_required, verified_token_required
)
from app.utils.redis_service import RedisClient
from app.utils.db_operations import handle_db_error

auth_bp = Blueprint('auth_bp', __name__)


@auth_bp.route('/user-public-info', methods=['GET'])
@json_required()
def check_email():
    """
    - required in query parameters:
        ?email="valid-email:str"
    """
    qp = QueryParams(request.args)
    email = StringHelpers(qp.get_first_value("email"))

    if not email:
        raise APIException.from_error(EM(qp.get_warings()).bad_request)

    valid, message = email.is_valid_email()
    if not valid:
        raise APIException.from_error(EM({"email": message}).bad_request)

    user = User.get_user_by_email(email.email_normalized)
    if user is None:
        raise APIException.from_error(EM({"email": f"user [{email.value}] not found"}).notFound)

    return JSONResponse(
        payload={**user.serialize_public_info()}
    ).to_json()


@auth_bp.route('/signup', methods=['POST'])  # normal signup
@json_required({"password": str, "fname": str, "lname": str})
@verified_token_required()
def signup(body, claims):  # from decorators functions
    """
    * PUBLIC ENDPOINT *
    Crea un nuevo usuario para la aplicación
    """
    email = claims.get('sub')  # email is the jwt id in verified token
    password = StringHelpers(body["password"])
    fname = StringHelpers(body["fname"])
    lname = StringHelpers(body["lname"])

    invalids = StringHelpers.validate_inputs({
        'password': password.is_valid_pw(),
        'fname': fname.is_valid_string(),
        'lname': lname.is_valid_string()
    })
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    user = User.get_user_by_email(email)

    if user:
        # ususario existente que ha sido invitado...
        if not user.signup_completed:
            # update user data
            try:
                user.fname = fname.value
                user.lname = lname.value
                user.password = password.value
                user.signup_completed = True
                db.session.commit()
            except SQLAlchemyError as e:
                handle_db_error(e)
            
            success, redis_error = RedisClient().add_jwt_to_blocklist(claims)  # bloquea verified-jwt
            if not success:
                raise APIException.from_error(EM(redis_error).service_unavailable)

            return JSONResponse(
                'user has completed registration process', 
                payload={'user': user.serialize_public_info()}
            ).to_json()
        # usuario ya ha completado la etapa de registro...

        success, redis_error = RedisClient().add_jwt_to_blocklist(claims)  # bloquea verified-jwt
        if not success:
            raise APIException.from_error(EM(redis_error).service_unavailable)

        # user already exists
        raise APIException.from_error(EM({"email": f"user: {email} already exists in the app"}).conflict)

    # nuevo usuario...
    try:
        new_user = User(
            email=email,
            email_confirmed=True,
            signup_completed=True,
            password=password.value,
            fname=fname.value,
            lname=lname.value
        )

        db.session.add(new_user)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    success, redis_error = RedisClient().add_jwt_to_blocklist(claims)  # bloquea verified-jwt
    if not success:
        raise APIException.from_error(EM(redis_error).service_unavailable)

    return JSONResponse(
        message="new user has been created", status_code=201, payload={'user': new_user.serialize_public_info()}
    ).to_json()


@auth_bp.route('/login/user', methods=['POST'])  # normal login
@json_required({"email": str, "password": str})
def login(body):  # body from json_required decorator

    email = StringHelpers(body["email"])
    pw = StringHelpers(body["password"])
    company_id = body.get("company_id", None)

    invalids = StringHelpers.validate_inputs({
        'email': email.is_valid_email(),
        'password': pw.is_valid_pw()
    })
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    # ?processing
    user = User.get_user_by_email(email.email_normalized)
    if not user:
        raise APIException.from_error(EM({"email": f"email {email.value} not found"}).notFound)

    if not check_password_hash(user._password_hash, pw.value):
        raise APIException.from_error(EM({"password": "password is invalid"}).wrong_password)

    if not user.is_enabled():
        raise APIException.from_error(EM({"email": "user hasn't completed registration proccess"}).unauthorized)

    additional_claims = {
        'user_access_token': True,
        'user_id': user.id
    }
    payload = {
        'user': user.serialize_all(),
    }

    if company_id:  # login with a company
        valid, msg = IntegerHelpers.is_valid_id(company_id)
        if not valid:
            raise APIException.from_error(EM({"company_id": msg}).bad_request)

        role = user.roles.join(Role.company).filter(Company.id == company_id).first()
        if role is None:
            raise APIException.from_error(EM({"company_id": f"company_id [{company_id}] not found"}).notFound)

        if not role.is_enabled():
            raise APIException.from_error(EM({"user_role": "user role has been deleted or disabled by admin user"}).unauthorized)

        additional_claims.update({
            'role_access_token': True,
            'role_id': role.id
        })
        payload.update({
            'company': role.company.serialize_all(),
            'role': role.serialize_all()
        })

    # *access-token
    access_token = create_access_token(
        identity=email.email_normalized,
        additional_claims=additional_claims
    )
    payload.update({'access_token': access_token})

    # ?response
    return JSONResponse(
        message="user logged in",
        payload=payload,
        status_code=201
    ).to_json()


@auth_bp.route('/email-validation', methods=['GET'])
@json_required()
def get_verification_code():
    """
    * PUBLIC ENDPOINT *
    Endpoint to request a new verification code to validate that email really exists
    required in query params:
        ?email="valid-email:str"
    """
    qp = QueryParams(request.args)
    email = StringHelpers(qp.get_first_value("email"))

    if not email:
        raise APIException.from_error(EM(qp.get_warings()).bad_request)
    
    valid, msg = email.is_valid_email()
    if not valid:
        raise APIException.from_error(EM({"email": msg}).bad_request)

    random_code = randint(100000, 999999)
    success, message = send_verification_email(user_email=email.email_normalized, verification_code=random_code)
    if not success:
        raise APIException.from_error(EM({"email_service": message}).service_unavailable)

    token = create_access_token(
        identity=email.email_normalized,
        additional_claims={
            'verification_code': random_code,
            'verification_token': True
        }
    )

    return JSONResponse(
        message='verification code sent to user',
        payload={
            'user_email': email.email_normalized,
            'user_validation_token': token
        }).to_json()


@auth_bp.route('/email-validation', methods=['PUT'])
@json_required({'code': int})
@verification_token_required()
def check_verification_code(body, claims):
    """
    ! PRIVATE ENDPOINT !
    endpoint: /check-verification-code
    methods: [PUT]
    description: endpoint to validate user's verification code sent to them by email.

    """

    if body['code'] != claims.get('verification_code'):
        raise APIException.from_error(EM({"verification_code": "verification code is invalid, try again"}).unauthorized)

    user = User.get_user_by_email(claims['sub'])
    if user and not user.email_confirmed:
        try:
            user.email_confirmed = True
            db.session.commit()

        except SQLAlchemyError as e:
            handle_db_error(e)

    success, redis_msg = RedisClient().add_jwt_to_blocklist(claims)  # invalida el uso del token una vez se haya validado del codigo
    if not success:
        raise APIException.from_error(EM(redis_msg).service_unavailable)

    verified_user_token = create_access_token(
        identity=claims['sub'],
        additional_claims={
            'verified_token': True
        }
    )
    payload = {'verified_user_token': verified_user_token}
    if user is not None:
        payload.update({'user': user.serialize_public_info()})

    return JSONResponse(
        "code verification success",
        payload=payload
    ).to_json()


@auth_bp.route("/change-password", methods=['PUT'])
@json_required({"password": str})
@verified_token_required()
def password_change(body, claims):
    """
    URL: /password-change
    methods: [PUT]
    description: endpoint to change user's password.

    """
    new_password = StringHelpers(body["password"])

    valid_pw, pw_msg = new_password.is_valid_pw()
    if not valid_pw:
        raise APIException.from_error(EM({"password": pw_msg}).bad_request)

    user = User.get_user_by_email(claims["sub"])
    if not user:
        raise APIException.from_error(EM({"email": f"user [{claims['sub']}] not found"}).notFound)

    try:
        user.password = new_password.value
        db.session.commit()

    except SQLAlchemyError as e:
        handle_db_error(e)

    success, redis_error = RedisClient().add_jwt_to_blocklist(claims)  # block jwt
    if not success:
        raise APIException.from_error(EM(redis_error).service_unavailable)

    return JSONResponse(message="user's password has been updated").to_json()


@auth_bp.route('/login/super-user', methods=['POST'])  # super-user login
@json_required({"password": str})
@verified_token_required()
def login_super_user(body, claims):
    """
    * VERIFIED TOKEN ONLY *
    required: {
        "password": password, <str>
    }
    """
    pw = StringHelpers(body["password"])
    valid, msg = pw.is_valid_pw()
    if not valid:
        raise APIException.from_error(EM({"password": msg}).bad_request)


    if claims["sub"] != 'luis.lucena89@gmail.com':  # ? debug - se debe agregar una condicion valida para produccion..
        raise APIException.from_error(EM({"email": "is not super user"}).unauthorized)

    user = User.get_user_by_email(claims["sub"])
    # ?processing
    if not user.email_confirmed:
        raise APIException.from_error(EM({"email": "email not confirmed"}).unauthorized)

    if not check_password_hash(user._password_hash, pw.value):
        raise APIException()

    # *super-user_access-token
    access_token = create_access_token(
        identity=claims["sub"],
        additional_claims={
            'user_access_token': True,
            'super_user': True,
            'user_id': user.id
        }
    )

    success, redis_error = RedisClient().add_jwt_to_blocklist(claims)
    if not success:
        raise APIException.from_error(EM(redis_error).service_unavailable)

    # ?response
    return JSONResponse(
        message="super user logged in",
        payload={
            "su_access_token": access_token
        },
        status_code=201
    ).to_json()


@auth_bp.route("/login/customer", methods=["POST"])
@json_required({"code": int, "company_id": int})
@verification_token_required()
def login_customer(body, claims):

    company_id = body["company_id"]

    if body["code"] != claims["verification_code"]:
        raise APIException.from_error(EM({"verification_code": "verification code is invalid, try again"}).unauthorized)

    user = User.get_user_by_email(claims["sub"])
    if not user or not user.is_enabled():
        raise APIException.from_error(EM({"email": "user hasn't completed registration process"}).user_not_active)

    valid, msg = IntegerHelpers.is_valid_id(company_id)
    if not valid:
        raise APIException.from_error(EM({"company_id": msg}).bad_request)
    
    company = db.session.query(Company).filter(Company.id==company_id).first()
    if not company:
        raise APIException.from_error(EM({"company_id": f"company_id [{company_id}] not found"}).notFound)

    access_token = create_access_token(
        identity=claims["sub"],
        additional_claims={
            "user_access_token":True,
            "customer_access_token": True,
            "user_id":user.id,
            "company_id": company.id
        }
    )

    return JSONResponse(
        message="customer logged in",
        payload={
            "access_token": access_token,
            "user": user.serialize_all()
        }
    ).to_json()