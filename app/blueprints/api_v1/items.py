from flask import Blueprint, request

#extensions
from app.models.main import Item, User, Company, Stock, Adquisition
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import ErrorMessages, JSONResponse, pagination_form
from app.utils.decorators import json_required, user_required
from app.utils.db_operations import handle_db_error, update_row_content, ValidRelations

items_bp = Blueprint('items_bp', __name__)


@items_bp.route('/', methods=['GET'])
@json_required()
@user_required(with_company=True)
def get_items(user): #user from user_required decorator

    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        item_id = int(request.args.get('item-id', -1))
    except:
        raise APIException('invalid format in query string, <int> is expected')

    if item_id == -1:
        itm = user.company.items.order_by(Item.name.asc()).paginate(page, limit)
        return JSONResponse(
            message="ok",
            payload={
                "items": list(map(lambda x: {**x.serialize(), **x.serialize_fav_image()}, itm.items)),
                **pagination_form(itm)
            }
        ).to_json()

    #item-id is present in query string
    itm = ValidRelations().user_item(user, item_id)

    #return item
    return JSONResponse(
        message="ok",
        payload={
            "item": {
                **itm.serialize(), 
                **itm.serialize_datasheet(), 
                "category": {**itm.category.serialize(), "path": itm.category.serialize_path()} if itm.category is not None else {}, 
                "global-stock": itm.get_item_stock()
            }
        }
    ).to_json()
    

@items_bp.route('/update-<int:item_id>', methods=['PUT'])
@json_required()
@user_required(with_company=True)
def update_item(item_id, user, body): #parameters from decorators

    ValidRelations().user_item(user, item_id)

    if "images" in body and isinstance(body["images"], list):
        body["images"] = {"urls": body["images"]}

    if "category_id" in body: #check if category_id is related with current user
        ValidRelations().user_category(user, body['category_id'])

    #update information
    to_update = update_row_content(Item, body)

    try:
        Item.query.filter(Item.id == item_id).update(to_update)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f'Item-id-{item_id} updated').to_json()


@items_bp.route('/create', methods=['POST'])
@json_required({"name":str, "category_id": int})
@user_required(with_company=True)
def create_item(user, body):

    ValidRelations().user_category(user, body['category_id'])

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

    return JSONResponse(f"new item with id: <{new_item.id}> created").to_json()


@items_bp.route('/delete-<int:item_id>', methods=['DELETE'])
@json_required()
@user_required(with_company=True)
def delete_item(item_id, user):

    itm = ValidRelations().user_item(user, item_id)

    try:
        db.session.delete(itm)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f"item id: <{item_id}> has been deleted").to_json()


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


@items_bp.route('/category-<int:category_id>', methods=['GET'])
@json_required()
@user_required(with_company=True)
def get_item_by_category(category_id, user):

    cat = ValidRelations().user_category(user, category_id)

    if cat.children != []:
        raise APIException(f"Category <{cat.name}> is a parent category") #change this to get all children's items, if necesary

    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
    except:
        raise APIException('invalid format in query string, <int> is expected')

    itms = db.session.query(Item).filter(Item.category_id == category_id).order_by(Item.name.asc()).paginate(page, limit)

    return JSONResponse(
        f"Items with category = {category_id}",
        payload={
            "items": list(map(lambda x: x.serialize(), itms.items)),
            **pagination_form(itms)
        }
    ).to_json()


@items_bp.route('/without-category', methods=['GET'])
@json_required()
@user_required(with_company=True)
def get_items_without_category(user):

    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
    except:
        raise APIException('invalid format in query string, <int> is expected')

    items = db.session.query(Item).select_from(User).join(User.company).join(Company.items).filter(Item.category_id == None, User.id == user.id).paginate(page, limit)

    return JSONResponse(
        "items without category assigned", 
        payload={
            "items": list(map(lambda x: x.serialize(), items.items)),
            **pagination_form(items)
        }
    ).to_json()


@items_bp.route('/search-by-name', methods=['GET'])
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