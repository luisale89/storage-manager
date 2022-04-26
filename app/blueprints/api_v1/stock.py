from flask import Blueprint, request
from app.models.main import Stock
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError

from app.utils.decorators import json_required, user_required
from app.utils.exceptions import APIException
from app.utils.helpers import JSONResponse, pagination_form
from app.utils.db_operations import ValidRelations, handle_db_error, update_row_content


stock_bp = Blueprint('stock_bp', __name__)

@stock_bp.route('/storage-id-<int:storage_id>', methods=['GET'])
@json_required()
@user_required(with_company=True)
def get_stock(user, storage_id):

    storage = ValidRelations().user_storage(user, storage_id)
    
    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        stock_id = int(request.args.get('stock_id', -1))
    except:
        raise APIException("invalid format in query string, <int> is expected")

    if stock_id == -1:
        all_stock = storage.stock.paginate(page, limit)

        return JSONResponse(
            message="ok",
            payload={
                "storage-stock": list(map(lambda x: x.item.serialize(), all_stock.items)),
                **pagination_form(all_stock)
            }
        ).to_json()

    stock  = storage.stock.filter(Stock.id == stock_id).first()

    return JSONResponse("ok", payload={
        'stock': stock.serialize(),
        'item': stock.item.serialize()
    }).to_json()


@stock_bp.route('/create', methods=['POST'])
@json_required({'storage_id': int, 'item_id': int})
@user_required(with_company=True)
def create_stock(user, body):

    item_id = body['item_id']
    storage_id = body['storage_id']

    ValidRelations().user_storage(user, storage_id)
    ValidRelations().user_item(user, item_id)

    to_add = update_row_content(Stock, body, silent=True)
    to_add.update({'_item_id': item_id, '_storage_id': storage_id})

    new_item = Stock(**to_add)

    try:
        db.session.add(new_item)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f"stock with id: <{new_item.id}> created").to_json()
