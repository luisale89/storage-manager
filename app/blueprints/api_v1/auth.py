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
    ErrorMessages, IntegerHelpers, JSONResponse, QueryParams, StringHelpers
)
from app.utils.email_service import send_verification_email
from app.utils.route_decorators import (
    json_required, verification_token_required, verified_token_required
)
from app.utils.redis_service import add_jwt_to_blocklist
from app.utils.db_operations import handle_db_error

auth_bp = Blueprint('auth_bp', __name__)


@auth_bp.route('/user-public-info', methods=['GET'])
@json_required()
def check_email():
    """
    - required in query parameters:
        ?email="valid-email:str"
    """
    error = ErrorMessages(parameters='email')
    qp = QueryParams(request.args)
    email = StringHelpers(qp.get_first_value("email"))

    if not email:
        error.custom_msg = f"{qp.get_warings()}"
        raise APIException.from_error(error.bad_request)

    valid, message = email.is_valid_email()
    if not valid:
        error.custom_msg = message
        raise APIException.from_error(error.bad_request)

    user = User.get_user_by_email(email.value.lower())
    if user is None:
        error.custom_msg = f'email: {email.value!r} not found in the database'
        raise APIException.from_error(error.notFound)

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

    invalids, msg = StringHelpers.validate_inputs({
        'password': password.is_valid_pw(),
        'fname': fname.is_valid_string(),
        'lname': lname.is_valid_string()
    })
    if invalids:
        raise APIException.from_error(
            ErrorMessages(parameters=invalids, custom_msg=f'invalid parameters in request. <{msg}>').bad_request)

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

            success, redis_error = add_jwt_to_blocklist(claims)  # bloquea verified-jwt
            if not success:
                raise APIException.from_error(
                    ErrorMessages(parameters='blocklist', custom_msg=redis_error).service_unavailable)

            return JSONResponse(
                'user has completed registration process', 
                payload={'user': user.serialize_public_info()}
            ).to_json()
        # usuario ya ha completado la etapa de registro...

        success, redis_error = add_jwt_to_blocklist(claims)  # bloquea verified-jwt
        if not success:
            raise APIException.from_error(
                ErrorMessages(parameters='blocklist', custom_msg=redis_error).service_unavailable)

        # user already exists
        raise APIException.from_error(
            ErrorMessages(parameters='email', custom_msg=f'user: {email} already exists in the app').conflict)

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

    success, redis_error = add_jwt_to_blocklist(claims)  # bloquea verified-jwt
    if not success:
        raise APIException.from_error(ErrorMessages(parameters='blocklist', custom_msg=redis_error).service_unavailable)

    return JSONResponse(
        message="new user has been created", status_code=201, payload={'user': new_user.serialize_public_info()}
    ).to_json()


@auth_bp.route('/login/user', methods=['POST'])  # normal login
@json_required({"email": str, "password": str})
def login(body):  # body from json_required decorator

    error = ErrorMessages()
    email = StringHelpers(body["email"])
    pw = StringHelpers(body["password"])
    company_id = IntegerHelpers(body.get("company_id", None))

    invalids, msg = StringHelpers.validate_inputs({
        'email': email.is_valid_email(),
        'password': pw.is_valid_pw()
    })
    if invalids:
        error.parameters.append(invalids)
        error.custom_msg = msg
        raise APIException.from_error(error.bad_request)

    # ?processing
    user = User.get_user_by_email(email.value.lower())
    if user is None:
        error.parameters.append('email')
        raise APIException.from_error(error.notFound)

    if not check_password_hash(user._password_hash, pw.value):
        error.parameters.append('password')
        raise APIException.from_error(error.wrong_password)

    if not user.is_enabled():
        error.parameters.append('email')
        raise APIException.from_error(error.unauthorized)

    additional_claims = {
        'user_access_token': True,
        'user_id': user.id
    }
    payload = {
        'user': user.serialize_all(),
    }

    if company_id:  # login with a company
        valid, msg = company_id.is_valid_id()
        if not valid:
            raise APIException.from_error(
                ErrorMessages(parameters='company_id', custom_msg=msg).bad_request
            )

        role = user.roles.join(Role.company).filter(Company.id == company_id.value).first()
        if role is None:
            raise APIException.from_error(
                ErrorMessages(parameters='company_id').notFound
            )

        if not role.is_enabled():
            raise APIException.from_error(
                ErrorMessages(
                    parameters='user_role',
                    custom_msg='user role has been deleted or disabled by admin user'
                ).unauthorized
            )

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
        identity=email.value.lower(),
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
    error = ErrorMessages(parameters="email")
    qp = QueryParams(request.args)
    email = StringHelpers(qp.get_first_value("email"))

    if not email:
        error.custom_msg = qp.get_warings()
        raise APIException.from_error(error.notAcceptable)
    
    valid, msg = email.is_valid_email()
    if not valid:
        error.custom_msg = msg
        raise APIException.from_error(error.bad_request)

    random_code = randint(100000, 999999)
    success, message = send_verification_email(user_email=email.value.lower(), verification_code=random_code)
    if not success:
        raise APIException.from_error(ErrorMessages(parameters='email-service', custom_msg=message).service_unavailable)

    token = create_access_token(
        identity=email.value.lower(),
        additional_claims={
            'verification_code': random_code,
            'verification_token': True
        }
    )

    return JSONResponse(
        message='verification code sent to user',
        payload={
            'user_email': email.value.lower(),
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
    email = claims.get('sub')

    if body['code'] != claims.get('verification_code'):
        raise APIException.from_error(
            ErrorMessages('verification_code', custom_msg='verification code is invalid, try again').unauthorized)

    user = User.get_user_by_email(email)
    if user and not user.email_confirmed:
        try:
            user.email_confirmed = True
            db.session.commit()

        except SQLAlchemyError as e:
            handle_db_error(e)

    success, redis_msg = add_jwt_to_blocklist(claims)  # invalida el uso del token una vez se haya validado del codigo
    if not success:
        raise APIException.from_error(ErrorMessages(parameters='blocklist', custom_msg=redis_msg).service_unavailable)

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
    email = claims['sub']
    error = ErrorMessages()

    valid_pw, pw_msg = new_password.is_valid_pw()
    if not valid_pw:
        error.parameters.append("password")
        error.custom_msg = pw_msg
        raise APIException.from_error(error.bad_request)

    user = User.get_user_by_email(email)
    if not user:
        error.parameters.append("email")
        raise APIException.from_error(error.notFound)

    try:
        user.password = new_password.value
        db.session.commit()

    except SQLAlchemyError as e:
        handle_db_error(e)

    success, redis_error = add_jwt_to_blocklist(claims)  # block jwt
    if not success:
        raise APIException.from_error(ErrorMessages(parameters='blocklist', custom_msg=redis_error).service_unavailable)

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
        raise APIException.from_error(ErrorMessages(parameters='password', custom_msg=msg).bad_request)

    email = claims['sub']
    user = User.get_user_by_email(email)

    if email != 'luis.lucena89@gmail.com':  # ? debug - se debe agregar una condicion valida para produccion..
        raise APIException("unauthorized user", status_code=401, app_result='error')

    # ?processing
    if not user.email_confirmed:
        raise APIException("user's email not validated", status_code=401)

    if not check_password_hash(user._password_hash, pw.value):
        raise APIException("wrong password", status_code=403)

    # *super-user_access-token
    access_token = create_access_token(
        identity=email,
        additional_claims={
            'user_access_token': True,
            'super_user': True,
            'user_id': user.id
        }
    )

    success, redis_error = add_jwt_to_blocklist(claims)
    if not success:
        raise APIException.from_error(ErrorMessages(parameters='blocklist', custom_msg=redis_error).service_unavailable)

    # ?response
    return JSONResponse(
        message="super user logged in",
        payload={
            "user_email": email,
            "su_access_token": access_token
        },
        status_code=201
    ).to_json()


@auth_bp.route("/login/customer", methods=["POST"])
@json_required({"code": int, "company_id": int})
@verification_token_required()
def login_customer(body, claims):

    error = ErrorMessages()
    email = claims["sub"]
    company_id = IntegerHelpers(body["company_id"])

    if body["code"] != claims["verification_code"]:
        error.parameters.append("verification_code")
        error.custom_msg = f"verification code is invalid, try again"
        raise APIException.from_error(error.unauthorized)

    user = User.get_user_by_email(email)
    if not user or not user.is_enabled():
        error.parameters.append("email")
        error.custom_msg = f"user has not completed registration proccess"
        raise APIException.from_error(error.user_not_active)

    valid, msg = company_id.is_valid_id()
    if not valid:
        error.parameters.append("company_id")
        error.custom_msg = msg
        raise APIException.from_error(error.bad_request)
    
    company = db.session.query(Company).filter(Company.id==company_id.value).first()
    if not company:
        error.parameters.append("company_id")
        raise APIException.from_error(error.notFound)

    access_token = create_access_token(
        identity=email,
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