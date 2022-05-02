from flask import Blueprint
from app.models.main import Stock
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError

from app.utils.decorators import json_required, user_required
from app.utils.helpers import JSONResponse
from app.utils.db_operations import ValidRelations, handle_db_error, update_row_content


stock_bp = Blueprint('stock_bp', __name__)

@stock_bp.route('/<int:stock_id>', methods=['GET'])
@json_required()
@user_required(with_company=True)
def get_stock(user, stock_id):
    
    stock = ValidRelations().user_stock(user, stock_id)

    return JSONResponse("ok", payload={
        'stock': {**stock.serialize(), **stock.storage.serialize(), 'existence': stock.get_stock_value()},
        'item': stock.item.serialize()
    }).to_json()


@stock_bp.route('/', methods=['POST'])
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
