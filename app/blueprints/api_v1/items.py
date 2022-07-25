from flask import Blueprint, request

#extensions
from app.models.main import AttributeValue, Attribute, Item, Company
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import func

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import ErrorMessages as EM, JSONResponse, QueryParams, StringHelpers, IntegerHelpers, Validations
from app.utils.route_decorators import json_required, role_required
from app.utils.db_operations import handle_db_error, update_row_content, Unaccent


items_bp = Blueprint('items_bp', __name__)


@items_bp.route('/', methods=['GET'])
@json_required()
@role_required()
def get_items(role):
    """
    query parameters:
    ?item_id:<int> - filter by item_id
    ?page:<int> - pagination page, default:1
    ?limit:<int> - pagination items limit, default:20
    ?cat_id:<int> - filter by category_id
    ?name_like:<str> - filter by name, %like%
    ?attr_value:<int> - filter by attribute value. Accept several ids with the same key. example: 
        ?attr_value=1&attr_value=2&...attr_value=n
        returns all coincidences
    """
    qp = QueryParams(request.args)

    item_id = qp.get_first_value('item_id', as_integer=True) #item_id or None
    if not item_id:
        q = db.session.query(Item).join(Item.company).join(Company.attributes).outerjoin(Item.attribute_values).\
            filter(Company.id == role.company.id)

        cat_id = qp.get_first_value('category_id', as_integer=True)
        if cat_id:
            valid, msg = IntegerHelpers.is_valid_id(cat_id)
            if not valid:
                raise APIException.from_error(EM({"category_id": msg}).bad_request)
            
            filter_category = role.company.get_category_by_id(cat_id)
            if not filter_category:
                raise APIException.from_error(EM({"category_id": f"id-{cat_id} not found"}).notFound)

            q = q.filter(Item.category_id.in_(filter_category.get_all_nodes())) #get all children-nodes of category
        
        attr_values = qp.get_all_integers('attr_value') #expecting integers
        if attr_values:
            q = q.filter(AttributeValue.id.in_(attr_values))

        name_like = StringHelpers(qp.get_first_value('name_like'))
        if name_like:
            q = q.filter(Unaccent(func.lower(Item.name)).like(f"%{name_like.no_accents.lower()}%"))

        page, limit = qp.get_pagination_params()
        q_items = q.order_by(Item.name.asc()).paginate(page, limit)
        return JSONResponse(
            message=qp.get_warings(),
            payload={
                "items": list(map(lambda x: x.serialize(), q_items.items)),
                **qp.get_pagination_form(q_items)
            }
        ).to_json()

    #item-id is present in query string
    valid, msg = IntegerHelpers.is_valid_id(item_id)
    if not valid:
        raise APIException.from_error(EM({"item_id": msg}).bad_request)

    target_item = role.company.get_item_by_id(item_id)
    if target_item is None:
        raise APIException.from_error(EM({"item_id": f"id-{item_id} not found"}).notFound)

    #return item
    return JSONResponse(
        message=qp.get_warings(),
        payload={
            "item": target_item.serialize_all()
        }
    ).to_json()
    

@items_bp.route('/<int:item_id>', methods=['PUT'])
@json_required()
@role_required(level=1)
def update_item(role, body, item_id): #parameters from decorators

    valid, msg = IntegerHelpers.is_valid_id(item_id)
    if not valid:
        raise APIException.from_error(EM({"item_id": msg}).bad_request)

    target_item = role.company.get_item_by_id(item_id)
    if target_item is None:
        raise APIException.from_error(EM({"item_id": f"id-{item_id} not found"}).notFound)

    if 'name' in body:
        name = StringHelpers(body["name"])
        name_exists = db.session.query(Item.name).filter(Unaccent(func.lower(Item.name)) == name.no_accents.lower(),\
            Company.id == role.company.id, Item.id != target_item.id).first()
        if name_exists:
            raise APIException.from_error(EM({"name": f"name already exists"}).conflict)

    #update information
    to_update, invalids = update_row_content(Item, body)
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    try:
        Item.query.filter(Item.id == item_id).update(to_update)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse('Item updated', payload={"item": target_item.serialize_all()}).to_json()


@items_bp.route('/', methods=['POST'])
@json_required({"name":str, "category_id": int})
@role_required(level=1)
def create_item(role, body):

    newItemName = StringHelpers(string=body["name"])
    categoryID = body["category_id"]

    invalids = Validations.validate_inputs({
        "newItemName": newItemName.is_valid_string(),
        "categoryID": IntegerHelpers.is_valid_id(categoryID)
    })
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    category = role.company.get_category_by_id(categoryID)
    if not category:
        raise APIException.from_error(EM({"category_id": f"id-{categoryID} not found"}).notFound)

    name_exists = db.session.query(Item).select_from(Company).join(Company.items).\
        filter(Unaccent(func.lower(Item.name)) == newItemName.no_accents.lower(), Company.id == role.company.id).first()
    if name_exists:
        raise APIException.from_error(EM({"name": f"name {newItemName.value} already exists"}).conflict)

    to_add, invalids = update_row_content(Item, body)
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    to_add.update({
        "company_id": role.company.id,
        "category_id": categoryID
    })

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
@role_required(level=1)
def delete_item(role, item_id=None):

    valid, msg = IntegerHelpers.is_valid_id(item_id)
    if not valid:
        raise APIException.from_error(EM({"item_id": msg}).bad_request)

    itemToDelete = role.company.get_item_by_id(item_id)
    if not itemToDelete:
        raise APIException.from_error(EM({"item_id": f"id-{item_id} not found"}).notFound)

    try:
        db.session.delete(itemToDelete)
        db.session.commit()

    except IntegrityError as ie:
        raise APIException.from_error(EM({"item_id": f"can't delete item_id:{item_id} - {ie}"}).conflict)

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f"item id: <{item_id}> has been deleted").to_json()


@items_bp.route('/<int:item_id>/attributes/values', methods=['PUT'])
@json_required({'values': list})
@role_required(level=1)
def update_item_attributeValue(role, body, item_id):

    valid, msg = IntegerHelpers.is_valid_id(item_id)
    if not valid:
        raise APIException.from_error(EM({"item_id": msg}).bad_request)
    
    targetItem = role.company.get_item_by_id(item_id)
    newValuesIDList = body['values']

    if not targetItem:
        raise APIException.from_error(EM({"item_id": f"id-{item_id} not found"}).notFound)

    if not newValuesIDList: #empty list clear all AttributeValues
        try:
            targetItem.attribute_values = []
            db.session.commit()

        except SQLAlchemyError as e:
            handle_db_error(e)
            
        return JSONResponse(
            message=f'item_id: {item_id} attributes has been updated',
            payload={
                'item': targetItem.serialize_all()
            }
        ).to_json()

    not_integer = [r for r in newValuesIDList if not isinstance(r, int)]
    if not_integer:
        raise APIException.from_error(EM({
            "values": f"list of values must include integers values only.. \
                <{not_integer}> was given"
            }).bad_request)

    if targetItem.category_id is None:
        raise APIException.from_error(EM({
            "item_id": f"Item_id-{item_id} has no category assigned"
        }).notAcceptable)

    attributeInstances = db.session.query(AttributeValue.attribute_id).\
        filter(AttributeValue.id.in_(newValuesIDList)).all()

    if len(attributeInstances) != len(set(attributeInstances)):
        raise APIException.from_error(EM({
            "attributes": f"any item must have only one value per attribute, \
                found duplicates values for the same attribute"
            }).bad_request)

    categoryAttributesList = targetItem.category.get_attributes(return_ids=True)

    newValuesInstances = db.session.query(AttributeValue).\
        filter(Attribute.id.in_(categoryAttributesList), AttributeValue.id.in_(newValuesIDList)).all()

    if not newValuesInstances:
        raise APIException.from_error(EM({"attributes": "no attributes were found in the database"}).notFound)

    try:
        targetItem.attribute_values = newValuesInstances
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message=f'item_id: {item_id} attributes has been updated',
        payload={
            'item': targetItem.serialize_all()
        }
    ).to_json()