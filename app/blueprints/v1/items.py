from flask import Blueprint, request

#extensions
from app.models.main import Acquisition, AttributeValue, Attribute, Item, Company, Provider
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
            q = q.filter(Unaccent(func.lower(Item.name)).like(f"%{name_like.unaccent.lower()}%"))

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

    invalids = Validations.validate_inputs({
        "item_id": IntegerHelpers.is_valid_id(item_id)
    })
    newRows, invalid_body = update_row_content(Item, body)
    invalids.update(invalid_body)
    if invalids:
        raise APIException.from_error(EM(invalids))

    target_item = role.company.get_item_by_id(item_id)
    if target_item is None:
        raise APIException.from_error(EM({"item_id": f"id-{item_id} not found"}).notFound)

    if 'name' in body:
        name = StringHelpers(body["name"])
        nameExists = db.session.query(Item.name).filter(Unaccent(func.lower(Item.name)) == name.unaccent.lower(),\
            Company.id == role.company.id, Item.id != target_item.id).first()
        if nameExists:
            raise APIException.from_error(EM({"name": f"name already exists"}).conflict)

    #update information
    try:
        Item.query.filter(Item.id == item_id).update(newRows)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse('Item updated', payload={"item": target_item.serialize_all()}).to_json()


@items_bp.route('/', methods=['POST'])
@json_required({"name":str})
@role_required(level=1)
def create_item(role, body):

    newItemName = StringHelpers(string=body["name"])
    newRows, invalids = update_row_content(Item, body)
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    newRows.update({
        "company_id": role.company.id
    })

    if "category_id" in body:
        categoryID = body["category_id"]
        valid, msg = IntegerHelpers.is_valid_id(categoryID)
        if not valid:
            raise APIException.from_error(EM({"category_id": msg}))
        
        category = role.company.get_category_by_id(categoryID)
        if not category:
            raise APIException.from_error(EM({"category_id": f"id-{categoryID} not found"}).notFound)

        newRows.update({
            "category_id": categoryID
        })
    
    nameExists = db.session.query(Item).select_from(Company).join(Company.items).\
        filter(Unaccent(func.lower(Item.name)) == newItemName.unaccent.lower(), Company.id == role.company.id).first()
    if nameExists:
        raise APIException.from_error(EM({"name": f"name {newItemName.value} already exists"}).conflict)

    new_item = Item(**newRows)

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


@items_bp.route("/<int:item_id>/category", methods=["PUT"])
@json_required({"category_id": int})
@role_required(level=1)
def update_item_category(role, body, item_id):

    categoryID = body["category_id"]
    invalids = Validations.validate_inputs({
        "category_id": IntegerHelpers.is_valid_id(categoryID),
        "item_id": IntegerHelpers.is_valid_id(item_id)
    })
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    target_item = db.session.query(Item).filter(Item.company_id == role.company.id, Item.id == item_id).first()
    if not target_item:
        raise APIException.from_error(EM({"item_id": f"item-{item_id} not found"}).notFound)

    if target_item.category:
        raise APIException.from_error(EM({"item_id": f"can't modify item's category, create a new item."}).conflict)

    try:
        target_item.category_id = categoryID
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message="item categroy updated"
    ).to_json()


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


@items_bp.route("/<int:item_id>/acquisitions", methods=["GET"])
@json_required()
@role_required(level=1)
def create_item_acq(role, item_id):

    valid, msg = IntegerHelpers.is_valid_id(item_id)
    if not valid:
        raise APIException.from_error(EM({"item_id": msg}).bad_request)

    target_item = db.session.query(Item).filter(Item.company_id == role.company.id).\
        filter(Item.id == item_id).first()

    if not target_item:
        raise APIException.from_error(EM({"item_id": f"ID-{item_id} not found"}).notFound)

    base_q = db.session.query(Acquisition).select_from(Company).join(Company.items).join(Item.acquisitions).\
        filter(Company.id == role.company.id, Item.id == item_id)
    
    qp = QueryParams(request.args)
    acq_id = qp.get_first_value("acquisition_id", as_integer=True)
    if not acq_id:

        # add filters here

        page, limit = qp.get_pagination_params()
        all_acq = base_q.paginate(page, limit)

        return JSONResponse(
            message=qp.get_warings(),
            payload={
                "item": target_item.serialize(),
                "acquisitions": list(map(lambda x:x.serialize(), all_acq.items)),
                **qp.get_pagination_form(all_acq)
            }
        ).to_json()

    #if acquisition_id is in query parameters
    valid, msg = IntegerHelpers.is_valid_id(acq_id)
    if not valid:
        raise APIException.from_error(EM({"acquisition_id": msg}).bad_request)

    target_acq = base_q.filter(Acquisition.id == acq_id).first()
    if not target_acq:
        raise APIException.from_error(EM({"acquisition_id": f"ID-{acq_id} not found"}).notFound)
    
    return JSONResponse(
        message=f"item-{item_id} acquisition-{acq_id}",
        payload={
            "acquisition": target_acq.serialize_all()
        }
    ).to_json()


@items_bp.route("/<int:item_id>/acquisitions", methods=["POST"])
@json_required({"storage_id": int})
@role_required(level=1)
def create_acquisition(role, body, item_id):

    storage_id = body["storage_id"]
    invalids = Validations.validate_inputs({
        "item_id": IntegerHelpers.is_valid_id(item_id),
        "storage_id": IntegerHelpers.is_valid_id(storage_id)
    })

    newRows, invalid_body = update_row_content(Acquisition, body)
    invalids.update(invalid_body)
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    target_item = db.session.query(Item).filter(Item.company_id == role.company.id, Item.id == item_id).first()
    if not target_item:
        raise APIException.from_error(EM({"item_id": f"ID-{item_id} not found"}).notFound)

    newRows.update({
        "item_id": item_id,
        "storage_id": storage_id
    })

    if "provider_id" in body:
        provider_id = body["provider_id"]
        valid, msg = IntegerHelpers.is_valid_id(provider_id)
        if not valid:
            raise APIException.from_error(EM({"provider_id": msg}).bad_request)

        target_provider = db.session.query(Provider.id).\
            filter(Provider.id == provider_id, Provider.company_id == role.company.id).first()
        
        if not target_provider:
            raise APIException.from_error(EM({"provider_id": f"ID-{provider_id} not found"}).notFound)

        newRows.update({
            "provider_id": provider_id
        })

    newAcquisition = Acquisition(**newRows)
    try:
        db.session.add(newAcquisition)
        db.session.commit()
    
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message="new acquisition created",
        payload={
            "acquisition": newAcquisition.serialize_all()
        },
        status_code=201
    ).to_json()


@items_bp.route("acquisitions/<int:acq_id>", methods=["PUT", "DELETE"])
@json_required()
@role_required(level=1)
def update_or_delete_acq(role, acq_id, body=None):

    invalids = Validations.validate_inputs({
        "acq_id": IntegerHelpers.is_valid_id(acq_id)
    })
    if body:
        newRows, invalid_body = update_row_content(Acquisition, body)
        invalids.update(invalid_body)
    if invalids:
        raise APIException.from_error(EM(invalids))

    target_acq = db.session.query(Acquisition.id).select_from(Company).join(Company.items).join(Item.acquisitions).\
        filter(Company.id == role.company.id, Acquisition.id == acq_id).first()
    
    if not target_acq:
        raise APIException.from_error(EM({"acquisition_id": f"ID-{acq_id} not found"}).notFound)

    if request.method == "DELETE":
        
        try:
            db.session.query(Acquisition).filter(Acquisition.id == acq_id).delete()
            db.session.commit()

        except IntegrityError as ie:
            raise APIException.from_error(EM({"acquisition_id": f"can't delete acquisition, {ie}"}).conflict)

        except SQLAlchemyError as e:
            handle_db_error(e)

        return JSONResponse(
            message=f"Acquisition-id-{acq_id} has been deleted"
        ).to_json()
    
    #if request.metod == "PUT"
    try:
        db.session.query(Acquisition).filter(Acquisition.id == acq_id).update(newRows)
        db.session.commit()
    
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message=f"Acquisition-id-{acq_id} has been updated"
    ).to_json()