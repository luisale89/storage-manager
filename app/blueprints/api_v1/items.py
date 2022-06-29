from flask import Blueprint, request

#extensions
from app.models.main import AttributeValue, Attribute, Category, Item, Company, Storage
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import func

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import ErrorMessages, JSONResponse, QueryParams
from app.utils.route_helper import get_pagination_params, pagination_form
from app.utils.route_decorators import json_required, role_required
from app.utils.db_operations import handle_db_error, update_row_content

items_bp = Blueprint('items_bp', __name__)

#*1
@items_bp.route('/', methods=['GET'])
@json_required()
@role_required()
def get_items(role):
    
    error = ErrorMessages()
    qp = QueryParams(request.args)
    item_id = qp.get_first_value('item_id') if 'item_id' in request.args else None

    if not item_id:
        page, limit = get_pagination_params()
        cat_id = qp.get_first_value('category_id') if 'category_id' in request.args else None
        storage_id = qp.get_first_value('storage_id') if 'storage_id' in request.args else None
        name_like = qp.get_first_value('name_like') if 'name_like' in request.args else None
        attr_values = qp.get_all_integers('attr_value') if 'attr_value' in request.args else None #expecting integers

        #main query
        q = db.session.query(Item).join(Item.company).join(Company.storages).join(Item.category).\
            join(Category.attributes).join(Item.attribute_values).\
                filter(Company.id == role.company.id)

        if cat_id:
            cat = role.company.get_category_by_id(cat_id)
            if cat is None:
                error.parameters.append('company_id')
            else:
                q = q.filter(Item.category_id.in_(cat.get_all_nodes())) #get all children-nodes of category

        if storage_id:
            storage = role.company.get_storage_by_id(storage_id)
            if storage is None:
                error.parameters.append('storage_id')
            else:
                q = q.filter(Storage.id == storage_id)

        if error.parameters:
            raise APIException.from_error(error.notFound)

        if attr_values:
            q = q.filter(AttributeValue.id.in_(attr_values))

        q_items = q.filter(func.lower(Item.name).like(f"%{name_like}%")).order_by(Item.name.asc()).paginate(page, limit)
        return JSONResponse(
            payload={
                "items": list(map(lambda x: x.serialize(), q_items.items)),
                **pagination_form(q_items)
            }
        ).to_json()

    #item-id is present in query string
    target_item = role.company.get_item_by_id(item_id)
    if target_item is None:
        error.parameters.append('item_id')
        raise APIException.from_error(error.notFound)

    #return item
    return JSONResponse(
        message="ok",
        payload={
            "item": target_item.serialize_all()
        }
    ).to_json()
    
#*2
@items_bp.route('/<int:item_id>', methods=['PUT'])
@json_required()
@role_required(level=1)
def update_item(role, body, item_id): #parameters from decorators

    error = ErrorMessages()

    target_item = role.company.get_item_by_id(item_id)
    if target_item is None:
        error.parameters.append('item_id')

    if "category_id" in body: #check if category_id is related with current role
        cat_id = body['category_id']
        cat = role.company.get_category_by_id(cat_id)
        if cat is None:
            error.parameters.append('category_id')
    
    if error.parameters:
        raise APIException.from_error(error.notFound)

    #update information
    to_update, invalids, msg = update_row_content(Item, body)
    if invalids:
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
        raise APIException.from_error(error.notFound)

    to_add, invalids, msg = update_row_content(Item, body)
    if invalids:
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

    error = ErrorMessages(parameters='item_id')
    itm = role.company.get_item_by_id(item_id)
    if itm is None:
        raise APIException.from_error(error.notFound)

    try:
        db.session.delete(itm)
        db.session.commit()
    except IntegrityError as ie:
        error.custom_msg = f"can't delete item_id:{item_id} - {ie}"
        raise APIException.from_error(error.conflict)
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f"item id: <{item_id}> has been deleted").to_json()


#*6
@items_bp.route('/<int:item_id>/attributes', methods=['PUT'])
@json_required({'attributes': list})
@role_required(level=1)
def update_item_attributeValue(role, body, item_id):

    target_item = role.company.get_item_by_id(item_id)
    new_attributes = body['attributes']
    error = ErrorMessages()

    if target_item is None:
        error.parameters.append('item_id')
        raise APIException.from_error(error.notFound)

    if not new_attributes: #empty list clear all attibute-values
        try:
            target_item.attribute_values = []
            db.session.commit()
        except SQLAlchemyError as e:
            handle_db_error(e)
        return JSONResponse(
            message=f'item_id: {item_id} attributes has been updated',
            payload={
                'item': target_item.serialize_all()
            }
        ).to_json()

    not_integer = [r for r in new_attributes if not isinstance(r, int)]
    if not_integer:
        error.parameters.append('attributes')
        error.custom_msg = f'list of attributes must include integers values only.. <{not_integer}> detected'
        raise APIException.from_error(error.bad_request)

    attributes_id = db.session.query(AttributeValue.attribute_id).filter(AttributeValue.id.in_(new_attributes)).all()
    if len(attributes_id) != len(set(attributes_id)):
        error.parameters.append('attributes')
        error.custom_msg = 'any item must have only one value per attribute, found duplicates values for the same attribute'
        raise APIException.from_error(error.bad_request)

    if target_item.category_id is None:
        error.parameters.append('item_id')
        error.custom_msg = f'Item_id: {item_id} has no category assigned'
        raise APIException.from_error(error.notAcceptable)

    new_values = db.session.query(AttributeValue).select_from(Category).join(Category.attributes).join(Attribute.attribute_values).\
        filter(Category.id == target_item.category.id, AttributeValue.id.in_(new_attributes)).all()

    if not new_values:
        error.parameters.append('attributes')
        error.custom_msg = f'no attributes were found in the database'
        raise APIException.from_error(error.notFound)

    try:
        target_item.attribute_values = new_values
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message=f'item_id: {item_id} attributes has been updated',
        payload={
            'item': target_item.serialize_all()
        }
    ).to_json()