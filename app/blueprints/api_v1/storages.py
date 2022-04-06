from flask import Blueprint, request, abort
from flask_jwt_extended import get_jwt

#extensions
from app.models.main import Storage
from app.extensions import db

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import JSONResponse, pagination_form
from app.utils.decorators import json_required, user_required
from app.utils.db_operations import get_user_by_id
from app.utils.validations import validate_inputs, validate_string


storages_bp = Blueprint('storages_bp', __name__)

@storages_bp.route('/', methods=['GET', 'PUT'])
@json_required()
@user_required()
def get_storages():

    claims = get_jwt()
    user = get_user_by_id(claims.get('user_id', None), company_required=True)
    try:
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('limit', 10))
        storage_id = int(request.args.get('storage-id', -1))
    except:
        raise APIException('invalid format in query string, <int> is expected')

    if storage_id == -1:
        if request.method == 'GET':
            s = user.company.storages.order_by(Storage.name.asc()).paginate(page, per_page) #return all storages,
            return JSONResponse(
                message="ok",
                payload={
                    "storages": list(map(lambda x: x.serialize(), s.items)),
                    **pagination_form(s)
                }
            ).to_json()


    #if an id has been passed in as a request arg.
    s = user.company.storages.filter(Storage.id == storage_id).first()
    if s is None:
        raise APIException(f"storage-id-{storage_id} not found", status_code=404, app_result="not_found")

    if request.method == 'GET': 
        #?return storage
        return JSONResponse(
            message="ok",
            payload={
                "storage": s.serialize()
            }
        ).to_json()

    if request.method == 'PUT':
        #?update storage information
        body = request.get_json() #new info in request body
        storage_name = body.get('storage_name', "")
        validate_inputs({
            "storage_name": validate_string(storage_name)
        })

        s.name = storage_name
        s.description = body.get('description', '')
        db.session.commit()

        return JSONResponse(f"Storage-id-{storage_id} has been updated").to_json()


@storages_bp.route('/create', methods=['POST'])
@json_required({"storage_name":str})
@user_required()
def create_new_storage():

    user = get_user_by_id(get_jwt().get('user_id', None), company_required=True)
    body = request.get_json(silent=True)
    storage_name = body['storage_name']
    
    try:
        new_storage = Storage(
            name = storage_name,
            description = body.get('description', ""),
            company = user.company
        )
        db.session.add(new_storage)
        db.session.commit()
    except:
        db.session.rollback()
        raise APIException("error")

    return JSONResponse("new storage created").to_json()


@storages_bp.route('/delete', methods=['DELETE'])
@json_required()
def delete_storage():

    return JSONResponse("developing...").to_json()