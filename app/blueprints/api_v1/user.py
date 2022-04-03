from flask import Blueprint, request
from flask_jwt_extended import get_jwt_identity

#extensions
from app.extensions import db
from sqlalchemy.exc import IntegrityError, DataError

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import normalize_names, JSONResponse
from app.utils.validations import validate_inputs, only_letters
from app.utils.decorators import json_required, user_required
from app.utils.db_operations import get_user_by_email

#models

user_bp = Blueprint('user_bp', __name__)


@user_bp.route('/', methods=['GET'])
@json_required()
@user_required()
def get_user():
    """
    * PRIVATE ENDPOINT *
    Obtiene los datos de perfil de un usuario.
    requerido: {} # header of the request includes JWT wich is linked to the user email
    respuesta: 
        "user": {
            "fname": string,
            "lname": string,
            "image": url,
            "home_address": dict,
            "phone": string,
            "user_since": utc-datetime,
        }
    """
    identity = get_jwt_identity()
    # user = get_user_by_email(identity) #get_jwt_indentity get the user id from jwt.
    user = get_user_by_email(email=identity)
    if user is None:
        raise APIException(f"email: {identity} not found in database", status_code=404, app_result="q_not_found")

    resp = JSONResponse(
        message="user's profile", 
        payload={
            "user": user.serialize(), 
            "identity": identity
        })

    return resp.to_json()


@user_bp.route('/update', methods=['PUT'])
@json_required({"fname":str, "lname":str, "home_address":dict, "image":str, "phone":str})
@user_required()
def update_user():

    user = get_user_by_email(get_jwt_identity()) #jwt identity = user_email

    body = request.get_json(silent=True)
    fname, lname, home_address, image, phone = \
    body['fname'], body['lname'], body['home_address'], body['image'], body['phone']
    
    validate_inputs({
        'fname': only_letters(fname, spaces=True, max_length=128),
        'lname': only_letters(lname, spaces=True, max_length=128)
    })

    if len(image) > 255: #?special validation, find out if you needo to do more validations on urls
        raise APIException("user img url is too long")
    
    user.fname = normalize_names(fname, spaces=True)
    user.lname = normalize_names(lname, spaces=True)
    user.home_address = home_address
    user.image = image
    user.phone = phone

    try:
        db.session.commit()
    except (IntegrityError, DataError) as e:
        db.session.rollback()
        raise APIException(e.orig.args[0], status_code=422) # integrityError or DataError info
    
    resp = JSONResponse(message="user's profile updated", payload={"user": user.serialize()})
    return resp.to_json()