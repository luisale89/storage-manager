from flask import Blueprint, request, current_app
from flask_jwt_extended import get_jwt

#extensions
from app.models.main import Item
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import JSONResponse, pagination_form, ErrorMessages
from app.utils.decorators import json_required, user_required
from app.utils.db_operations import get_user_by_id, update_row_content, ValidRelations

items_bp = Blueprint('items_bp', __name__)


@items_bp.route('/', methods=['GET'])
@json_required()
@user_required()
def get_items():

    claims = get_jwt()
    user = get_user_by_id(claims.get('user_id', None), company_required=True)

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
                "items": list(map(lambda x: x.serialize(), itm.items)),
                **pagination_form(itm)
            }
        ).to_json()

    #item-id is present in query string
    itm = user.company.items.filter(Item.id == item_id).first()
    if itm is None:
        raise APIException(f"item-id-{item_id} not found", status_code=404, app_result="error")

    #return item
    return JSONResponse(
        message="ok",
        payload={
            "item": {
                **itm.serialize(), 
                **itm.serialize_datasheet(), 
                "category": itm.category.serialize() if itm.category is not None else {}, 
                "global-stock": itm.get_item_stock()
            }
        }
    ).to_json()
    

@items_bp.route('/update-<int:item_id>', methods=['PUT'])
@json_required()
@user_required()
def update_item(item_id):

    claims = get_jwt()
    user = get_user_by_id(claims.get('user_id', None), company_required=True)
    body = request.get_json() #expecting information in body request

    itm = user.company.items.filter(Item.id == item_id).first()
    if itm is None:
        raise APIException(f"{ErrorMessages().notFound} <item_id>:<{item_id}>", status_code=404)

    sku = body.get('sku', '').lower()
    if sku != "":
        if Item.check_sku_exists(user.company.id, sku) and itm.sku != sku:
            raise APIException(f"{ErrorMessages().conflict} <sku:{sku}>", status_code=409)

    if "category_id" in body: #check if category_id is related with current user
        ValidRelations().user_category(user.id, body['category_id'])

    #update information
    to_update = update_row_content(Item, body)

    try:
        Item.query.filter(Item.id == item_id).update(to_update)
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(e) #log error
        raise APIException(ErrorMessages().dbError, status_code=500)

    return JSONResponse(f'Item-id-{item_id} updated').to_json()


@items_bp.route('/create', methods=['POST'])
@json_required({"name":str, "sku": str})
@user_required()
def create_new_item():

    user = get_user_by_id(get_jwt().get('user_id', None), company_required=True)
    body = request.get_json()

    sku = body.get('sku').lower()
    if Item.check_sku_exists(user.company.id, sku):
        raise APIException(f"{ErrorMessages().conflict} <sku:{sku}>", status_code=409)

    if "category_id" in body: #check if category_id is related with current user
        ValidRelations().user_category(user.id, body['category_id'])
    
    to_add = update_row_content(Item, body, silent=True)
    to_add["_company_id"] = user.company.id # add current user company_id to dict

    new_item = Item(**to_add)

    try:
        db.session.add(new_item)
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(e) #log error
        raise APIException(ErrorMessages().dbError, status_code=500)

    return JSONResponse("new item created").to_json()
