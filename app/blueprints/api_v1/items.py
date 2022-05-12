from flask import Blueprint, request

#extensions
from app.models.main import Item, Company, Stock, Storage
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import ErrorMessages, JSONResponse, str_to_int
from app.utils.route_helper import get_pagination_params, pagination_form
from app.utils.decorators import json_required, user_required
from app.utils.db_operations import handle_db_error, update_row_content, ValidRelations

items_bp = Blueprint('items_bp', __name__)


@items_bp.route('/', methods=['GET'])
@items_bp.route('/<int:item_id>', methods=['GET'])
@json_required()
@user_required()
def get_items(role, item_id=None): #user from user_required decorator

    if item_id == None:
        page, limit = get_pagination_params()
        category_id = str_to_int(request.args.get('category', 0))
        storage_id = str_to_int(request.args.get('storage', 0))
        name_like = request.args.get('like', '').lower()

        if category_id == None:
            raise APIException(ErrorMessages('int', 'category').invalidFormat())
        if storage_id == None:
            raise APIException(ErrorMessages('int', 'storage').invalidFormat())
        #main query
        q = db.session.query(Item).join(Item.company).join(Item.category).\
            outerjoin(Item.stock).outerjoin(Stock.storage)

        if category_id != 0:
            cat = ValidRelations().company_category(role.company.id, category_id)
            q = q.filter(Item.category_id.in_(cat.get_all_nodes())) #get all children-nodes of category

        if storage_id != 0:
            ValidRelations().company_storage(role.company.id, storage_id)
            q = q.filter(Storage.id == storage_id)


        items = q.filter(Company.id == role.company.id, Item.name.like(f"%{name_like}%")).order_by(Item.name.asc()).paginate(page, limit)
        return JSONResponse(
            payload={
                "items": list(map(lambda x: x.serialize(), items.items)),
                **pagination_form(items)
            }
        ).to_json()

    #item-id is present in query string
    itm = ValidRelations().company_item(role.company.id, item_id)

    #return item
    return JSONResponse(
        message="ok",
        payload={
            "item": itm.serialize_all()
        }
    ).to_json()
    

@items_bp.route('/<int:item_id>', methods=['PUT'])
@json_required()
@user_required(level=1)
def update_item(role, body, item_id=None): #parameters from decorators

    ValidRelations().company_item(role.company.id, item_id)

    if "images" in body and isinstance(body["images"], list):
        body["images"] = {"urls": body["images"]}

    if "category_id" in body: #check if category_id is related with current role
        ValidRelations().company_category(role.company.id, body['category_id'])

    #update information
    to_update = update_row_content(Item, body)

    try:
        Item.query.filter(Item.id == item_id).update(to_update)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f'Item-id-{item_id} updated').to_json()


@items_bp.route('/', methods=['POST'])
@json_required({"name":str, "category_id": int})
@user_required(level=1)
def create_item(role, body):

    ValidRelations().company_category(role.company.id, body['category_id'])

    if "images" in body and isinstance(body["images"], list):
        body["images"] = {"urls": body["images"]}
    
    to_add = update_row_content(Item, body, silent=True)
    to_add["_company_id"] = role.company.id # add current role company_id to dict

    new_item = Item(**to_add)

    try:
        db.session.add(new_item)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        payload={'item': new_item.serialize_all()},
        status_code=201
    ).to_json()


@items_bp.route('/<int:item_id>', methods=['DELETE'])
@json_required()
@user_required(level=1)
def delete_item(role, item_id=None):

    itm = ValidRelations().company_item(role.company.id, item_id)

    try:
        db.session.delete(itm)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f"item id: <{item_id}> has been deleted").to_json()


@items_bp.route('/bulk-delete', methods=['PUT'])
@json_required({'to_delete': list})
@user_required(level=1)
def items_bulk_delete(role, body): #from decorators

    to_delete = body['to_delete']

    not_integer = [r for r in to_delete if not isinstance(r, int)]
    if not_integer != []:
        raise APIException(f"list of item_ids must be only a list of integer values, invalid: {not_integer}")

    itms = role.company.items.filter(Item.id.in_(to_delete)).all()
    if itms == []:
        raise APIException("no item has been found", status_code=404)

    try:
        for i in itms:
            db.session.delete(i)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f"Items {[i.id for i in itms]} has been deleted").to_json()


@items_bp.route('<int:item_id>/storages', methods=['GET'])
@json_required()
@user_required()
def get_item_stocks(role, item_id=None):

    itm = ValidRelations().company_item(role.company.id, item_id)
    page, limit = get_pagination_params()

    stocks = itm.stock.paginate(page, limit)

    return JSONResponse(
        message="ok",
        payload={
            "stock": list(map(lambda x: {'storage': x.storage.serialize(), **x.serialize()}, stocks.items)),
            **pagination_form(stocks)
        }
    ).to_json()