from flask import Blueprint, request, current_app
from flask_jwt_extended import get_jwt

#extensions
from app.models.main import Storage, Shelf
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import JSONResponse, pagination_form, ErrorMessages
from app.utils.decorators import json_required, user_required
from app.utils.db_operations import ValidRelations, update_row_content


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


@storages_bp.route('/update-<int:storage_id>', methods=['PUT'])
@storages_bp.route('/create', methods=['POST'])
@json_required()
@user_required(with_company=True)
def update_storage(body, user, storage_id=None):

    if request.method == 'PUT':
        ValidRelations().user_storage(user, storage_id)
        to_update = update_row_content(Storage, body)

        try:
            Storage.query.filter(Storage.id == storage_id).update(to_update)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(e) #log error
            raise APIException(ErrorMessages().dbError, status_code=500)

        return JSONResponse(f'Storage-id-{storage_id} updated').to_json()

    else:
        to_add = update_row_content(Storage, body, silent=True)
        to_add["_company_id"] = user.company.id # add current user company_id to dict

        new_item = Storage(**to_add)

        try:
            db.session.add(new_item)
            db.session.commit()
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(e) #log error
            raise APIException(ErrorMessages().dbError, status_code=500)

        return JSONResponse(f"new storage with id: <{new_item.id}> created").to_json()


@storages_bp.route('/delete-<int:storage_id>', methods=['DELETE'])
@json_required()
@user_required(with_company=True)
def delete_storage(user, storage_id):

    strg = ValidRelations().user_storage(user, storage_id)

    try:
        db.session.delete(strg)
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(e)
        raise APIException(ErrorMessages().dbError, status_code=500)

    return JSONResponse(f"storage id: <{storage_id}> has been deleted").to_json()


@storages_bp.route('/<int:storage_id>/shelves', methods=['GET'])
@json_required()
@user_required(with_company=True)
def get_storage_shelves(storage_id, user):

    try:
        page = int(request.args.get('page', 1))
        limit = int(request.args.get('limit', 20))
    except:
        raise APIException('invalid format in query string, <int> is expected')

    strg = ValidRelations().user_storage(user, storage_id)
    shelves = strg.shelves.order_by(Shelf.id.asc()).paginate(page, limit)

    return JSONResponse(
        message="ok",
        payload={
            "shelves": list(map(lambda x: {**x.serialize(), **x.serialize_data()}, shelves.items)),
            **pagination_form(shelves)
        }
    ).to_json()


@storages_bp.route('/<int:storage_id>/shelves/create', methods=['POST'])
@json_required()
@user_required(with_company=True)
def create_shelf(storage_id, user, body):

    ValidRelations().user_storage(user, storage_id)
    if "parent_id" in body:
        ValidRelations().user_shelf(user, body['parent_id'])
    
    to_add = update_row_content(Shelf, body, silent=True)
    to_add["_storage_id"] = storage_id # add current user company_id to dict
    new_item = Shelf(**to_add)

    try:
        db.session.add(new_item)
        db.session.commit()
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(e) #log error
        raise APIException(ErrorMessages().dbError, status_code=500)

    return JSONResponse(f"new shelf with id: <{new_item.id}> created").to_json()


@storages_bp.route('/<int:storage_id>/shelf/<int:shelf_id>/stock', methods=['GET'])
@json_required()
@user_required()
def get_shelf_stock(storage_id, shelf_id):

    return JSONResponse(f"developing for storage-id-{storage_id}/shelf-id-{shelf_id} ...").to_json()
