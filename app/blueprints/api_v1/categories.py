from flask import Blueprint

#extensions
from app.models.main import Category, Item
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError

#utils
from app.utils.helpers import JSONResponse
from app.utils.decorators import json_required, role_required
from app.utils.db_operations import handle_db_error, update_row_content, ValidRelations
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

    #item-id is present in the route
    cat = ValidRelations().company_category(role.company.id, category_id)
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

    ValidRelations().company_category(role.company.id, category_id)

    #update information
    if "parent_id" in body:
        ValidRelations().company_category(role.company.id, body['parent_id'])

    to_update = update_row_content(Category, body)

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

    if "parent_id" in body:
        ValidRelations().company_category(role.company.id, body['parent_id'])

    to_add = update_row_content(Category, body, silent=True)
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

    cat = ValidRelations().company_category(role.company.id, category_id)

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

    cat = ValidRelations().company_category(role.company.id, category_id)
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