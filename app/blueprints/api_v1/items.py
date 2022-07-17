from flask import Blueprint

#extensions
from app.models.main import Acquisition, AttributeValue, Attribute, Item, Company, Provider
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import func

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import ErrorMessages, JSONResponse, QueryParams, StringHelpers
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
    
    error = ErrorMessages()
    qp = QueryParams()

    item_id = qp.get_first_value('item_id', as_integer=True) #item_id or None
    if not item_id:
        q = db.session.query(Item).join(Item.company).join(Company.attributes).outerjoin(Attribute.attribute_values).\
            filter(Company.id == role.company.id)

        cat_id = qp.get_first_value('category_id', as_integer=True)
        if cat_id:
            filter_category = role.company.get_category_by_id(cat_id)
            if not filter_category:
                error.parameters.append('company_id')
                raise APIException.from_error(error.notFound)

            q = q.filter(Item.category_id.in_(filter_category.get_all_nodes())) #get all children-nodes of category
        
        attr_values = qp.get_all_integers('attr_value') #expecting integers
        if attr_values:
            q = q.filter(AttributeValue.id.in_(attr_values))

        name_like = qp.get_first_value('name_like')
        if name_like:
            sh = StringHelpers(string=name_like)
            q = q.filter(Unaccent(func.lower(Item.name)).like(f"%{sh.no_accents.lower()}%"))

        page, limit = qp.get_pagination_params()
        q_items = q.order_by(Item.name.asc()).paginate(page, limit)
        return JSONResponse(
            message=f"ok\n{qp.ignored}",
            payload={
                "items": list(map(lambda x: x.serialize(), q_items.items)),
                **qp.get_pagination_form(q_items)
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
    

@items_bp.route('/<int:item_id>', methods=['PUT'])
@json_required()
@role_required(level=1)
def update_item(role, body, item_id): #parameters from decorators

    error = ErrorMessages()

    target_item = role.company.get_item_by_id(item_id)
    if target_item is None:
        error.parameters.append('item_id')    
        raise APIException.from_error(error.notFound)

    if 'name' in body:
        name = StringHelpers(body["name"])
        name_exists = db.session.query(Item.name).filter(Unaccent(func.lower(Item.name)) == name.no_accents.lower(),\
            Company.id == role.company.id, Item.id != target_item.id).first()
        if name_exists:
            error.parameters.append("name")
            error.custom_msg = f"'name': {name.string} already exists"
            raise APIException.from_error(error.conflict)

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


@items_bp.route('/', methods=['POST'])
@json_required({"name":str, "category_id": int})
@role_required(level=1)
def create_item(role, body):

    error = ErrorMessages()
    sh = StringHelpers(string=body["name"])

    category_id = body['category_id']
    category = role.company.get_category_by_id(category_id)
    if category is None:
        error.parameters.append('category_id')
        raise APIException.from_error(error.notFound)

    name_exists = db.session.query(Item.name).filter(Unaccent(func.lower(Item.name)) == sh.no_accents.lower(),\
        Company.id == role.company.id).first()
    if name_exists:
        error.parameters.append("name")
        error.custom_msg = f"'name':{sh.string} already exists"
        raise APIException.from_error(error.conflict)

    to_add, invalids, msg = update_row_content(Item, body)
    if invalids:
        error.parameters.append(invalids)
        error.custom_msg = msg
        raise APIException.from_error(error.bad_request)

    to_add.update({
        "company_id": role.company.id,
        "category_id": category_id
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


@items_bp.route('/<int:item_id>/attributes/values', methods=['PUT'])
@json_required({'values': list})
@role_required(level=1)
def update_item_attributeValue(role, body, item_id):

    error = ErrorMessages()

    target_item = role.company.get_item_by_id(item_id)
    new_values_id = body['values']

    if target_item is None:
        error.parameters.append('item_id')
        raise APIException.from_error(error.notFound)

    if not new_values_id: #empty list clear all AttributeValues
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

    not_integer = [r for r in new_values_id if not isinstance(r, int)]
    if not_integer:
        error.parameters.append('values')
        error.custom_msg = f'list of values must include integers values only.. <{not_integer}> detected'
        raise APIException.from_error(error.bad_request)

    if target_item.category_id is None:
        error.parameters.append('item_id')
        error.custom_msg = f'Item_id: {item_id} has no category assigned'
        raise APIException.from_error(error.notAcceptable)

    attributes_id = db.session.query(AttributeValue.attribute_id).filter(AttributeValue.id.in_(new_values_id)).all()
    if len(attributes_id) != len(set(attributes_id)):
        error.parameters.append('attributes')
        error.custom_msg = 'any item must have only one value per attribute, found duplicates values for the same attribute'
        raise APIException.from_error(error.bad_request)

    category_attributes_ids = target_item.category.get_attributes(return_ids=True)

    new_values = db.session.query(AttributeValue).\
        filter(Attribute.id.in_(category_attributes_ids), AttributeValue.id.in_(new_values_id)).all()

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


@items_bp.route("/acquisitions", methods=["GET"])
@json_required()
@role_required()
def get_item_acquisitions(role, ):

    """
    query parameters: 
    ?item_id:<int> = filter acquisitions by item_id
    ?provider_id:<int> = filter acquisitions by provider_id
    ?page:<int> = pagination page - default:1
    ?limit:<int> = pagination items limit - default:20
    """
    error = ErrorMessages(parameters="item_id")
    qp = QueryParams()
    sh = StringHelpers()
    
    main_q = db.session.query(Acquisition).join(Acquisition.item).join(Item.company).join(Acquisition.provider).\
        filter(Company.id == role.company.id)

    provider_id = qp.get_first_value("provider_id", as_integer=True)
    if provider_id:
        filter_provider = role.company.providers.filter(Provider.id == provider_id).first()
        if not filter_provider:
            error.parameters.append("provider_id")
            raise APIException.from_error(error.notFound)

        main_q = main_q.filter(Provider.id == provider_id)
    
    item_id = qp.get_first_value("item_id", as_integer=True)
    if item_id:
        filter_item = role.company.items.filter(Item.id == item_id).first()
        if not filter_item:
            error.parameters.append("item_id")
            raise APIException.from_error(error.notFound)

        main_q = main_q.filter(Item.id == item_id)

    page, limit = qp.get_pagination_params()
    acquisitions = main_q.paginate(page, limit)
    return JSONResponse(
        message="ok",
        payload={
            "acquisitions": list(map(lambda x:x.serialize(), acquisitions.items)),
            **qp.get_pagination_form(acquisitions)
        }
    ).to_json()