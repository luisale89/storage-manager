from flask import Blueprint, request

#extensions
from app.models.main import Item, Company, Stock, Storage
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import ErrorMessages, JSONResponse, str_to_int
from app.utils.route_helper import get_pagination_params, pagination_form
from app.utils.decorators import json_required, role_required
from app.utils.db_operations import handle_db_error, update_row_content

items_bp = Blueprint('items_bp', __name__)

#*1
@items_bp.route('/', methods=['GET'])
@items_bp.route('/<int:item_id>', methods=['GET'])
@json_required()
@role_required()
def get_items(role, item_id=None): #user from role_required decorator
    
    error = ErrorMessages()

    if item_id is None:
        page, limit = get_pagination_params()
        category_id = str_to_int(request.args.get('category', 0)) #return None if invalid int
        storage_id = str_to_int(request.args.get('storage', 0)) #return None if invalid int
        name_like = request.args.get('like', '').lower()

        if category_id == None:
            error.parameters.append('category')

        if storage_id == None:
            error.parameters.append('company')

        if error.parameters != []:
            error.custom_msg = 'Invalid format in request'
            raise APIException.from_error(error.bad_request)
    
        #main query
        q = db.session.query(Item).join(Item.company).join(Item.category).\
            outerjoin(Item.stock).outerjoin(Stock.storage)

        if category_id != 0:
            cat = role.company.get_category_by_id(category_id)
            if cat is None:
                error.parameters.append('company_id')
            else:
                q = q.filter(Item.category_id.in_(cat.get_all_nodes())) #get all children-nodes of category

        if storage_id != 0:
            # ValidRelations().company_storage(role.company.id, storage_id)
            storage = role.company.get_storage_by_id(storage_id)
            if storage is None:
                error.parameters.append('storage_id')
            else:
                q = q.filter(Storage.id == storage_id)

        if error.parameters != []:
            raise APIException.from_error(error.notFound)

        items = q.filter(Company.id == role.company.id, func.lower(Item.name).like(f"%{name_like}%")).order_by(Item.name.asc()).paginate(page, limit)
        return JSONResponse(
            payload={
                "items": list(map(lambda x: x.serialize(), items.items)),
                **pagination_form(items)
            }
        ).to_json()

    #item-id is present in query string
    itm = role.company.get_item_by_id(item_id)
    if itm is None:
        error.parameters.append('item_id')
        raise APIException.from_error(error.notFound)

    #return item
    return JSONResponse(
        message="ok",
        payload={
            "item": itm.serialize_all()
        }
    ).to_json()
    
#*2
@items_bp.route('/<int:item_id>', methods=['PUT'])
@json_required()
@role_required(level=1)
def update_item(role, body, item_id): #parameters from decorators

    error = ErrorMessages()

    itm = role.company.get_item_by_id(item_id)
    if itm is None:
        error.parameters.append('item_id')

    if "category_id" in body: #check if category_id is related with current role
        cat_id = body['category_id']
        cat = role.company.get_category_by_id(cat_id)
        if cat is None:
            error.parameters.append('category_id')
    
    if error.parameters != []:
        raise APIException.from_error(error.notFound)

    if "images" in body and isinstance(body["images"], list):
        body["images"] = {"images": body["images"]}

    #update information
    to_update, invalids, msg = update_row_content(Item, body)
    if invalids != []:
        error.parameters.append(invalids)
        error.custom_msg = msg
        raise APIException.from_error(error.bad_request)

    try:
        Item.query.filter(Item.id == item_id).update(to_update)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f'Item-id-{item_id} updated').to_json()

#*3
@items_bp.route('/', methods=['POST'])
@json_required({"name":str, "category_id": int})
@role_required(level=1)
def create_item(role, body):

    error = ErrorMessages()
    category_id = body['category_id']
    category = role.company.get_category_by_id(category_id)

    if category is None:
        error.parameters.append('category_id')

    if "images" in body and isinstance(body["images"], list):
        body["images"] = {"images": body["images"]}

    if error.parameters != []:
        raise APIException.from_error(error.notFound)
    
    to_add, invalids, msg = update_row_content(Item, body)
    if invalids != []:
        error.parameters.append(invalids)
        error.custom_msg = msg
        raise APIException.from_error(error.bad_request)

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

#*4
@items_bp.route('/<int:item_id>', methods=['DELETE'])
@json_required()
@role_required(level=1)
def delete_item(role, item_id=None):

    itm = role.company.get_item_by_id(item_id)
    if itm is None:
        raise APIException.from_error(ErrorMessages(parameters='item_id').notFound)

    try:
        db.session.delete(itm)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f"item id: <{item_id}> has been deleted").to_json()

#*5
@items_bp.route('/bulk-delete', methods=['PUT'])
@json_required({'to_delete': list})
@role_required(level=1)
def items_bulk_delete(role, body): #from decorators

    error = ErrorMessages()
    to_delete = body['to_delete']

    not_integer = [r for r in to_delete if not isinstance(r, int)]
    if not_integer != []:
        error.parameters.append(not_integer)
        error.custom_msg = 'Invalid format in request'
        raise APIException.from_error(error.bad_request)

    itms = role.company.items.filter(Item.id.in_(to_delete)).all()
    if itms == []:
        error.parameters.append(to_delete)
        raise APIException.from_error(error.notFound)

    try:
        for i in itms:
            db.session.delete(i)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f"Items {[i.id for i in itms]} has been deleted").to_json()

#*6
@items_bp.route('<int:item_id>/storages', methods=['GET'])
@json_required()
@role_required()
def get_item_stocks(role, item_id=None):

    itm = role.company.get_item_by_id(item_id)
    if itm is None:
        raise APIException.from_error(ErrorMessages(parameters='item_id').notFound)

    page, limit = get_pagination_params()
    stocks = itm.stock.paginate(page, limit)

    return JSONResponse(
        message="ok",
        payload={
            "stock": list(map(lambda x: {'storage': x.storage.serialize(), **x.serialize()}, stocks.items)),
            **pagination_form(stocks)
        }
    ).to_json()