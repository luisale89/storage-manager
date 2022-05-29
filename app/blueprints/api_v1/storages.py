from flask import Blueprint

#extensions
from app.models.main import Shelf, Storage, Stock, Item
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError

#utils
from app.utils.helpers import JSONResponse, ErrorMessages
from app.utils.route_helper import get_pagination_params, pagination_form
from app.utils.route_decorators import json_required, role_required
from app.utils.db_operations import (
    update_row_content, handle_db_error
)
from app.utils.exceptions import APIException


storages_bp = Blueprint('storages_bp', __name__)

#*1
@storages_bp.route('/', methods=['GET'])
@storages_bp.route('/<int:storage_id>', methods=['GET'])
@json_required()
@role_required()
def get_storages(role, storage_id=None):

    if storage_id == None:
        page, limit = get_pagination_params()
        store = role.company.storages.order_by(Storage.name.asc()).paginate(page, limit) #return all storages,
        return JSONResponse(
            message="ok",
            payload={
                "storages": list(map(lambda x: x.serialize(), store.items)),
                **pagination_form(store)
            }
        ).to_json()

    #if an id has been passed in as a request arg.
    storage = role.company.get_storage_by_id(storage_id)
    if storage is None:
        raise APIException.from_error(ErrorMessages(parameters='storage_id').notFound)

    #?return storage
    return JSONResponse(
        message="ok",
        payload={
            "storage": storage.serialize_all()
        }
    ).to_json()

#*2
@storages_bp.route('/', methods=['POST'])
@json_required({'name': str})
@role_required()
def create_storage(role, body):

    to_add, invalids, msg = update_row_content(Storage, body)
    if invalids != []:
        raise APIException.from_error(ErrorMessages(parameters=invalids, custom_msg=msg).bad_request)

    to_add["_company_id"] = role.company.id # add current user company_id to dict
    new_item = Storage(**to_add)

    try:
        db.session.add(new_item)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        payload={'storage': new_item.serialize()}, status_code=201
    ).to_json()

#*3
@storages_bp.route('/<int:storage_id>', methods=['PUT'])
@json_required()
@role_required()
def update_storage(role, body, storage_id=None):

    storage = role.company.get_storage_by_id(storage_id)
    if storage is None:
        raise APIException.from_error(ErrorMessages(parameters='storage_id').notFound)

    to_update, invalids, msg = update_row_content(Storage, body)
    if invalids != []:
        raise APIException.from_error(ErrorMessages(parameters=invalids, custom_msg=msg).bad_request)

    try:
        Storage.query.filter(Storage.id == storage_id).update(to_update)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f'Storage-id-{storage_id} updated').to_json()

#*4
@storages_bp.route('/<int:storage_id>', methods=['DELETE'])
@json_required()
@role_required()
def delete_storage(role, storage_id):

    storage = role.company.get_storage_by_id(storage_id)
    if storage is None:
        raise APIException.from_error(ErrorMessages('storage_id').notFound)

    try:
        db.session.delete(storage)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f"storage id: <{storage_id}> has been deleted").to_json()

#*5
@storages_bp.route('/<int:storage_id>/items', methods=['POST'])
@json_required({"item_id": int})
@role_required()
def create_item_in_storage(role, body, storage_id):

    error = ErrorMessages()
    item_id = body['item_id']
    item = role.company.get_item_by_id(item_id)
    if item is None:
        error.parameters.append('item_id')

    storage = role.company.get_storage_by_id(storage_id)
    if storage is None:
        error.parameters.append('storage_id')

    if error.parameters != []:
        raise APIException.from_error(error.notFound)

    stock = db.session.query(Stock).join(Stock.item).join(Stock.storage).filter(Item.id == item_id, Storage.id == storage.id).first()
    if stock is not None:
        error.parameters.append('item_id')
        error.custom_msg = f"item id:<{item_id}> already exists in current storage"
        raise APIException.from_error(error.conflict)

    to_add, invalids, msg = update_row_content(Stock, body)
    if invalids != []:
        raise APIException.from_error(ErrorMessages(parameters=invalids, custom_msg=msg).bad_request)
    
    to_add.update({'_item_id': item_id, '_storage_id': storage.id})

    new_stock = Stock(**to_add)

    try:
        db.session.add(new_stock)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        payload={
            'item': item.serialize_all(),
            'stock': new_stock.serialize()
        },
        status_code=201
    ).to_json()