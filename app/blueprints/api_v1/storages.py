from flask import Blueprint

#extensions
from app.models.main import Shelf, Storage, Stock, Item
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError

#utils
from app.utils.helpers import JSONResponse
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
    strg = ValidRelations().company_storage(user.company.id, storage_id)

    #?return storage
    return JSONResponse(
        message="ok",
        payload={
            "storage": strg.serialize(),
            'total-items-in-stock': strg.stock.count()
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

    return JSONResponse(
        payload={'storage': new_item.serialize()}
    ).to_json()


@storages_bp.route('/<int:storage_id>', methods=['PUT'])
@json_required()
@user_required(with_company=True)
def update_storage(body, user, storage_id=None):

    ValidRelations().company_storage(user.company.id, storage_id)
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

    strg = ValidRelations().company_storage(user.company.id, storage_id)

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

    storage = ValidRelations().company_storage(user.company.id, storage_id)

    page, limit = get_pagination_params()
    stocks = storage.stock.paginate(page, limit)

    return JSONResponse(
        message="ok",
        payload={
            "items-in-stock": list(map(lambda x: {
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
    storage = ValidRelations().company_storage(user.company.id, storage_id)

    itm = db.session.query(Stock).join(Stock.item).join(Stock.storage).filter(Item.id == item_id, Storage.id == storage.id).first()
    if itm is not None:
        raise APIException(message=f"item id:<{item_id}> already exists in current storage", status_code=409)

    ValidRelations().company_item(user.company.id, item_id)

    to_add = update_row_content(Stock, body, silent=True)
    to_add.update({'_item_id': item_id, '_storage_id': storage.id})

    new_stock = Stock(**to_add)

    try:
        db.session.add(new_stock)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        payload={
            "item-in-stock": {
                **new_stock.serialize(),
                **new_stock.item.serialize(detail=True),
                "inventory": 0.0
            }
        },
        status_code=201
    ).to_json()


@storages_bp.route('/<int:storage_id>/items/<int:item_id>', methods=['GET'])
@json_required()
@user_required(with_company=True)
def get_item_in_storage(user, storage_id, item_id):

    stock = ValidRelations().company_stock(user.company.id, item_id, storage_id)

    return JSONResponse(
        message='ok',
        payload={
            "item-in-stock": {
                **stock.serialize(),
                **stock.item.serialize(detail=True),
                "inventory": stock.get_stock_value()
            }
        }
    ).to_json()


@storages_bp.route('/<int:storage_id>/items/<int:item_id>', methods=['PUT'])
@json_required()
@user_required(with_company=True)
def update_item_in_storage(user, body, storage_id, item_id):

    stock = ValidRelations().company_stock(user.company.id, item_id, storage_id)
    to_update = update_row_content(Stock, body)

    try:
        Stock.query.filter(Stock.id == stock.id).update(to_update)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f"stock of item-id :<{item_id}> updated").to_json()


@storages_bp.route('/<int:storage_id>/items/<int:item_id>', methods=['DELETE'])
@json_required()
@user_required(with_company=True)
def delete_item_from_storage(user, storage_id, item_id):

    stock = ValidRelations().company_stock(user.company.id, item_id, storage_id)

    try:
        db.session.delete(stock)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f'item-id: <{item_id}> removed of storage-id:<{storage_id}>').to_json()


@storages_bp.route('/<int:storage_id>/shelves', methods=['GET'])
@storages_bp.route('/<int:storage_id>/shelves/<int:shelf_id>', methods=['GET'])
@json_required()
@user_required(with_company=True)
def get_shelves_in_storage(user, storage_id, shelf_id=None):

    if shelf_id == None:
        page, limit = get_pagination_params()

        storage = ValidRelations().company_storage(user.company.id, storage_id)
        shelves = storage.shelves.filter(Shelf.parent_id == None).order_by(Shelf.name.asc()).paginate(page, limit)

        return JSONResponse(payload={
            "shelves": list(map(lambda x:x.serialize(), shelves.items)),
            **pagination_form(shelves)
        }).to_json()

    shelf = ValidRelations().storage_shelf(user.company.id, storage_id, shelf_id)
    return JSONResponse(payload={
        "shelf": {**shelf.serialize(), "inventory": list(map(lambda x:x.serialize(), shelf.inventories))}
    }).to_json()