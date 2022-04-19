from flask import Blueprint, request, current_app
from flask_jwt_extended import get_jwt

#extensions
from app.models.main import User, Storage, Company
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import JSONResponse, pagination_form, ErrorMessages
from app.utils.decorators import json_required, user_required
from app.utils.db_operations import ValidRelations, update_row_content
from app.utils.validations import validate_inputs, validate_string


storages_bp = Blueprint('storages_bp', __name__)

@storages_bp.route('/', methods=['GET'])
@json_required()
@user_required(with_company=True)
def get_storages(user):

    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        storage_id = int(request.args.get('storage-id', -1))
    except:
        raise APIException('invalid format in query string, <int> is expected')

    if storage_id == -1:
        store = user.company.storages.order_by(Storage.name.asc()).paginate(page, limit) #return all storages,
        return JSONResponse(
            message="ok",
            payload={
                "storages": list(map(lambda x: x.serialize(), store.items)),
                **pagination_form(store)
            }
        ).to_json()

    #if an id has been passed in as a request arg.
    strg = ValidRelations().user_storage(user, storage_id)

    #?return storage
    return JSONResponse(
        message="ok",
        payload={
            "storage": strg.serialize()
        }
    ).to_json()


@storages_bp.route('/create', methods=['POST'])
@json_required()
def create_storage():

    return JSONResponse("developing...").to_json()


@storages_bp.route('/delete', methods=['DELETE'])
@json_required()
def delete_storage():

    return JSONResponse("developing...").to_json()


@storages_bp.route('/<int:storage_id>/shelves', methods=['GET', 'PUT'])
@json_required()
@user_required()
def get_storage_shelves(storage_id):

    return JSONResponse(f"developing for storage-id-{storage_id} ...").to_json()


@storages_bp.route('/<int:storage_id>/shelves/create', methods=['POST'])
@json_required({"shelf_name": str})
@user_required()
def create_shelf(storage_id):

    return JSONResponse(f"developing for storage-id-{storage_id} ...").to_json()


@storages_bp.route('/<int:storage_id>/shelf/<int:shelf_id>/stock', methods=['GET'])
@json_required()
@user_required()
def get_shelf_stock(storage_id, shelf_id):

    return JSONResponse(f"developing for storage-id-{storage_id}/shelf-id-{shelf_id} ...").to_json()
