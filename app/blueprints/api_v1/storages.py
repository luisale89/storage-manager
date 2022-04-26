from flask import Blueprint, request

#extensions
from app.models.main import Storage, Shelf
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import JSONResponse, pagination_form
from app.utils.decorators import json_required, user_required
from app.utils.db_operations import (
    ValidRelations, update_row_content, handle_db_error
)


storages_bp = Blueprint('storages_bp', __name__)

@storages_bp.route('/', methods=['GET'])
@json_required()
@user_required(with_company=True)
def get_storages(user):

    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
        storage_id = int(request.args.get('storage-id', -1))
    except:
        raise APIException('invalid format in query string, <int> is expected')

    if storage_id == -1:
        store = user.company.storages.order_by(Storage.name.asc()).paginate(page, limit) #return all storages,
        return JSONResponse(
            message="ok",
            payload={
                "storages": list(map(lambda x: x.serialize(), store.items)),
                **pagination_form(store)
            }
        ).to_json()

    #if an id has been passed in as a request arg.
    strg = ValidRelations().user_storage(user, storage_id)

    #?return storage
    return JSONResponse(
        message="ok",
        payload={
            "storage": strg.serialize()
        }
    ).to_json()


@storages_bp.route('/create', methods=['POST'])
@json_required({'name': str})
@user_required(with_company=True)
def create_storage(user, body):

    to_add = update_row_content(Storage, body, silent=True)
    to_add["_company_id"] = user.company.id # add current user company_id to dict
    new_item = Storage(**to_add)

    try:
        db.session.add(new_item)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f"storage with id: <{new_item.id}> created").to_json()


@storages_bp.route('/update-<int:storage_id>', methods=['PUT'])
@json_required()
@user_required(with_company=True)
def update_storage(body, user, storage_id=None):

    ValidRelations().user_storage(user, storage_id)
    to_update = update_row_content(Storage, body)

    try:
        Storage.query.filter(Storage.id == storage_id).update(to_update)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f'Storage-id-{storage_id} updated').to_json()


@storages_bp.route('/delete-<int:storage_id>', methods=['DELETE'])
@json_required()
@user_required(with_company=True)
def delete_storage(user, storage_id):

    strg = ValidRelations().user_storage(user, storage_id)

    try:
        db.session.delete(strg)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f"storage id: <{storage_id}> has been deleted").to_json()


