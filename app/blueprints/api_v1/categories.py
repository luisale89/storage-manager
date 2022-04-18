from crypt import methods
from re import L
from flask import Blueprint, request, current_app

#extensions
from app.models.main import Category
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import JSONResponse, pagination_form, ErrorMessages
from app.utils.decorators import json_required, user_required
from app.utils.db_operations import get_user_by_id, update_row_content, ValidRelations

categories_bp = Blueprint('categories_bp', __name__)


@categories_bp.route('/', methods=['GET'])
@json_required()
@user_required()
def get_categories(user):

    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        cat_id = int(request.args.get('category-id', -1))
    except:
        raise APIException('invalid format in query string, <int> is expected')

    if cat_id == -1:
        cat = user.company.categories.filter(Category.parent_id == None).order_by(Category.name.asc()).paginate(page, limit)
        return JSONResponse(
            message="ok",
            payload={
                "categories": list(map(lambda x: {
                    **x.serialize(), 
                    "sub-categories": list(map(lambda y: y.serialize(), x.children))
                }, cat.items)),
                **pagination_form(cat)
            }
        ).to_json()

    #item-id is present in query string
    cat = user.company.categories.filter(Category.id == cat_id).first()
    if cat is None:
        raise APIException(f"{ErrorMessages().notFound} <category-id>:<{cat_id}>", status_code=404, app_result="error")

    #return item
    return JSONResponse(
        message="ok",
        payload={
            "category": {
                **cat.serialize(),
                "sub-categories": list(map(lambda y: y.serialize(), cat.children)),
                "path": cat.serialize_path()
            }
        }
    ).to_json()


@categories_bp.route('/update-<int:category_id>', methods=['PUT'])
@json_required()
@user_required(with_company=True)
def update_category(category_id, user, body):

    ValidRelations().user_category(user, category_id)

    #update information
    if "parent_id" in body:
        p = ValidRelations().user_category(user, body['parent_id'])
        itms = p.items.count()
        if itms != 0:
            raise APIException(f"Category: <{p.name}> can't be a parent category, has {itms} item(s) assigned")

    to_update = update_row_content(Category, body)

    try:
        Category.query.filter(Category.id == category_id).update(to_update)
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(e) #log error
        raise APIException(ErrorMessages().dbError, status_code=500)

    return JSONResponse(f'Category-id-{category_id} updated').to_json()


@categories_bp.route('/create', methods=['POST'])
@json_required({'name': str})
@user_required(with_company=True)
def create_category(user, body):

    name = body.get('name')
    if Category.check_name_exists(user.company.id, name):
        raise APIException(f"{ErrorMessages().conflict} <name:{name}>", status_code=409)

    if "parent_id" in body:
        ValidRelations().user_category(user, body['parent_id'])

    to_add = update_row_content(Category, body, silent=True)
    to_add["_company_id"] = user.company.id # add current user company_id to dict

    new_category = Category(**to_add)

    try:
        db.session.add(new_category)
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(e) #log error
        raise APIException(ErrorMessages().dbError, status_code=500)

    return JSONResponse(f"new category with id:{new_category.id} created").to_json()


@categories_bp.route('/delete-<int:category_id>', methods=['DELETE'])
@json_required()
@user_required()
def delete_item(category_id, user):

    cat = ValidRelations().user_category(user, category_id)

    try:
        db.session.delete(cat)
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(e)
        raise APIException(ErrorMessages().dbError, status_code=500)

    return JSONResponse(f"Category id: <{category_id}> has been deleted").to_json()