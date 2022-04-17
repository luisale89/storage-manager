from flask import Blueprint, request, current_app
from flask_jwt_extended import get_jwt

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
def get_categories():

    user = get_user_by_id(get_jwt().get('user_id', None), company_required=True)

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
                "categories": list(map(lambda x: x.serialize(), cat.items)),
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
                **cat.serialize_path(),
                "children": list(map(lambda x:x.serialize(), cat.children)),
                "items": cat.items.count()
            }
        }
    ).to_json()