from flask import Blueprint

#extensions
from app.models.main import Category, Item
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError
from app.utils.exceptions import APIException

#utils
from app.utils.helpers import ErrorMessages, JSONResponse
from app.utils.route_decorators import json_required, role_required
from app.utils.db_operations import handle_db_error, update_row_content
from app.utils.route_helper import get_pagination_params, pagination_form

categories_bp = Blueprint('categories_bp', __name__)

#*1
@categories_bp.route('/', methods=['GET'])
@categories_bp.route('/<int:category_id>', methods=['GET'])
@json_required()
@role_required()
def get_categories(role, category_id=None):

    if category_id == None:
        cat = role.company.categories.filter(Category.parent_id == None).order_by(Category.name.asc()).all() #root categories only
        
        return JSONResponse(
            message="ok",
            payload={
                "categories": list(map(lambda x: x.serialize_children(), cat))
            }
        ).to_json()

    #category-id is present in the route
    cat = role.company.get_category_by_id(category_id)
    if cat is None:
        raise APIException.from_error(ErrorMessages("category_id").notFound)
    resp = {
        "category": {
            **cat.serialize(), 
            "path": cat.serialize_path(), 
            "sub-categories": list(map(lambda x: x.serialize(), cat.children)),
            "attributes": list(map(lambda x: x.serialize(), cat.get_attributes()))
        }
    }

    #return item
    return JSONResponse(
        message="ok",
        payload=resp
    ).to_json()

#*2
@categories_bp.route('/<int:category_id>', methods=['PUT'])
@json_required()
@role_required()
def update_category(role, body, category_id=None):

    #validate information
    error = ErrorMessages()
    cat = role.company.get_category_by_id(category_id)
    if cat is None:
        error.parameters.append('category_id')

    parent_id = body.get('parent_id', None)
    if parent_id is not None:
        parent = role.company.get_category_by_id(parent_id)
        if parent is None:
            error.parameters.append('parent_id')

    if error.parameters != []:
        raise APIException.from_error(error.notFound)

    #update information
    to_update, invalids, msg = update_row_content(Category, body)
    if invalids != []:
        error.parameters.append(invalids)
        error.custom_msg = msg
        raise APIException(error.bad_request)

    try:
        Category.query.filter(Category.id == category_id).update(to_update)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f'Category-id-{category_id} updated').to_json()

#*3
@categories_bp.route('/', methods=['POST'])
@json_required({'name': str})
@role_required()
def create_category(role, body):

    parent_id = body.get('parent_id', None)
    if parent_id is not None:
        parent = role.company.get_category_by_id(parent_id)
        if parent is None:
            raise APIException.from_error(ErrorMessages("parent_id").notFound)

    to_add, invalids, msg = update_row_content(Category, body)
    if invalids != []:
        raise APIException.from_error(ErrorMessages(parameters=invalids, custom_msg=msg).bad_request)

    to_add["_company_id"] = role.company.id # add current user company_id to dict

    new_category = Category(**to_add)

    try:
        db.session.add(new_category)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        payload={"category": new_category.serialize()},
        status_code=201
    ).to_json()

#*4
@categories_bp.route('/<int:category_id>', methods=['DELETE'])
@json_required()
@role_required()
def delete_category(role, category_id=None):

    cat = role.company.get_category_by_id(category_id)
    if cat is None:
        raise APIException.from_error(ErrorMessages("category_id").notFound)

    try:
        db.session.delete(cat)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f"Category id: <{category_id}> has been deleted").to_json()

#*5
@categories_bp.route('/<int:category_id>/items', methods=['GET'])
@json_required()
@role_required()
def get_items_by_category(role, category_id=None):

    cat = role.company.get_category_by_id(category_id)
    if cat is None:
        raise APIException.from_error(ErrorMessages("category_id").notFound)

    page, limit = get_pagination_params()
    itms = db.session.query(Item).filter(Item.category_id.in_(cat.get_all_nodes())).order_by(Item.name.asc()).paginate(page, limit)

    return JSONResponse(
        f"all items with category id == <{category_id}> and children categories",
        payload={
            **pagination_form(itms),
            "items": list(map(lambda x: x.serialize(), itms.items)),
            "category": {
                **cat.serialize(),
                "path": cat.serialize_path(),
                "attributes": list(map(lambda x: x.serialize(), cat.attributes))
            }
        }
    ).to_json()