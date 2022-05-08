from flask import Blueprint, request

#extensions
from app.models.main import Item, User, Company
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import JSONResponse
from app.utils.route_helper import get_pagination_params, pagination_form
from app.utils.decorators import json_required, user_required
from app.utils.db_operations import handle_db_error, update_row_content, ValidRelations

items_bp = Blueprint('items_bp', __name__)


@items_bp.route('/', methods=['GET'])
@items_bp.route('/<int:item_id>', methods=['GET'])
@json_required()
@user_required(with_company=True)
def get_items(user, item_id=None): #user from user_required decorator

    if item_id == None:
        page, limit = get_pagination_params()

        itm = user.company.items.order_by(Item.name.asc()).paginate(page, limit)
        return JSONResponse(
            message="ok",
            payload={
                "items": list(map(lambda x: x.serialize(), itm.items)),
                **pagination_form(itm)
            }
        ).to_json()

    #item-id is present in query string
    itm = ValidRelations().company_item(user.company.id, item_id)

    #return item
    return JSONResponse(
        message="ok",
        payload={
            "item": itm.serialize_all()
        }
    ).to_json()
    

@items_bp.route('/<int:item_id>', methods=['PUT'])
@json_required()
@user_required(with_company=True)
def update_item(item_id, user, body): #parameters from decorators

    ValidRelations().company_item(user.company.id, item_id)

    if "images" in body and isinstance(body["images"], list):
        body["images"] = {"urls": body["images"]}

    if "category_id" in body: #check if category_id is related with current user
        ValidRelations().company_category(user.company.id, body['category_id'])

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
@user_required(with_company=True)
def create_item(user, body):

    ValidRelations().company_category(user.company.id, body['category_id'])

    if "images" in body and isinstance(body["images"], list):
        body["images"] = {"urls": body["images"]}
    
    to_add = update_row_content(Item, body, silent=True)
    to_add["_company_id"] = user.company.id # add current user company_id to dict

    new_item = Item(**to_add)

    try:
        db.session.add(new_item)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        payload={'item': new_item.serialize()},
        status_code=201
    ).to_json()


@items_bp.route('/<int:item_id>', methods=['DELETE'])
@json_required()
@user_required(with_company=True)
def delete_item(item_id, user):

    itm = ValidRelations().company_item(user.company.id, item_id)

    try:
        db.session.delete(itm)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f"item id: <{item_id}> has been deleted").to_json()


@items_bp.route('<int:item_id>/stocks', methods=['GET'])
@json_required()
@user_required(with_company=True)
def get_item_stocks(user, item_id):

    itm = ValidRelations().company_item(user.company.id, item_id)
    page, limit = get_pagination_params()

    stocks = itm.stock.paginate(page, limit)

    return JSONResponse(
        message="ok",
        payload={
            "stock": list(map(lambda x: x.storage.serialize(), stocks.items)),
            **pagination_form(stocks)
        }
    ).to_json()


@items_bp.route('/bulk-delete', methods=['PUT'])
@json_required({'to_delete': list})
@user_required(with_company=True)
def items_bulk_delete(user, body): #from decorators

    to_delete = body['to_delete']

    not_integer = [r for r in to_delete if not isinstance(r, int)]
    if not_integer != []:
        raise APIException(f"list of item_ids must be only a list of integer values, invalid: {not_integer}")

    itms = user.company.items.filter(Item.id.in_(to_delete)).all()
    if itms == []:
        raise APIException("no item has been found", status_code=404)

    try:
        for i in itms:
            db.session.delete(i)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f"Items {[i.id for i in itms]} has been deleted").to_json()


@items_bp.route('/search', methods=['GET'])
@json_required()
@user_required(with_company=True)
def search_item_by_name(user):

    rq_name = request.args.get('item_name', '').lower()

    items = db.session.query(Item).select_from(User).\
        join(User.company).join(Company.items).\
            filter(User.id == user.id, Item.name.like(f"%{rq_name}%")).\
                order_by(Item.name.asc()).limit(10) #limit 10 results

    return JSONResponse(f'results like <{rq_name}>', payload={
        'items': list(map(lambda x: x.serialize(), items))
    }).to_json()