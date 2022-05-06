from flask import Blueprint, request

#extensions
from app.models.main import Storage, Stock, Item
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError

#utils
from app.utils.helpers import JSONResponse, ErrorMessages
from app.utils.route_helper import get_pagination_params, pagination_form
from app.utils.decorators import json_required, user_required
from app.utils.db_operations import (
    ValidRelations, update_row_content, handle_db_error
)
from app.utils.exceptions import APIException


storages_bp = Blueprint('storages_bp', __name__)


@storages_bp.route('/', methods=['GET'])
@storages_bp.route('/<int:storage_id>', methods=['GET'])
@json_required()
@user_required(with_company=True)
def get_storages(user, storage_id=None):

    if storage_id == None:
        page, limit = get_pagination_params()
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
            "storage": strg.serialize(),
            'items': strg.stock.count()
        }
    ).to_json()


@storages_bp.route('/', methods=['POST'])
@json_required({'name': str})
@user_required(with_company=True)
def create_storage(user, body):

    to_add = update_row_content(Storage, body, silent=True)
    to_add["_company_id"] = user.company.id # add current user company_id to dict
    new_item = Storage(**to_add)

    try:
        db.session.add(new_item)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f"storage with id: <{new_item.id}> created").to_json()


@storages_bp.route('/<int:storage_id>', methods=['PUT'])
@json_required()
@user_required(with_company=True)
def update_storage(body, user, storage_id=None):

    ValidRelations().user_storage(user, storage_id)
    to_update = update_row_content(Storage, body)

    try:
        Storage.query.filter(Storage.id == storage_id).update(to_update)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f'Storage-id-{storage_id} updated').to_json()


@storages_bp.route('/<int:storage_id>', methods=['DELETE'])
@json_required()
@user_required(with_company=True)
def delete_storage(user, storage_id):

    strg = ValidRelations().user_storage(user, storage_id)

    try:
        db.session.delete(strg)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f"storage id: <{storage_id}> has been deleted").to_json()


@storages_bp.route('/<int:storage_id>/items', methods=['GET'])
@json_required()
@user_required(with_company=True)
def get_storage_stock(user, storage_id):

    storage = ValidRelations().user_storage(user, storage_id)

    page, limit = get_pagination_params()
    stocks = storage.stock.paginate(page, limit)

    return JSONResponse(
        message="ok",
        payload={
            "items": list(map(lambda x: {
                **x.item.serialize()
            }, stocks.items)),
            **pagination_form(stocks),
        }
    ).to_json()


@storages_bp.route('/<int:storage_id>/items', methods=['POST'])
@json_required({"item_id": int})
@user_required(with_company=True)
def create_item_in_storage(user, body, storage_id):

    item_id = int(body.get('item_id'))
    storage = ValidRelations().user_storage(user, storage_id)

    itm = db.session.query(Stock).join(Stock.item).join(Stock.storage).filter(Item.id == item_id, Storage.id == storage.id).first()
    if itm is not None:
        raise APIException(message=f"item id:<{item_id}> already exists in current storage", status_code=403)

    ValidRelations().user_item(user, item_id)

    to_add = update_row_content(Stock, body, silent=True)
    to_add.update({'_item_id': item_id, '_storage_id': storage.id})

    new_item = Stock(**to_add)

    try:
        db.session.add(new_item)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f"New item with id:<{item_id}> added to storage id:<{storage.id}>").to_json()


@storages_bp.route('/<int:storage_id>/items/<int:item_id>', methods=['GET'])
@json_required()
@user_required(with_company=True)
def get_item_in_storage(user, storage_id, item_id):

    stock = ValidRelations().company_stock(user.company.id, item_id, storage_id)

    return JSONResponse(
        message='ok',
        payload={
            "item": {
                **stock.serialize(),
                **stock.item.serialize(detail=True),
                "stock": stock.get_stock_value()
            }
        }
    ).to_json()


@storages_bp.route('/<int:storage_id>/items/<int:item_id>', methods=['PUT'])
@json_required()
@user_required(with_company=True)
def update_item_in_storage(user, body, storage_id, item_id):

    storage = ValidRelations(user, storage_id)
    item = ValidRelations()