from flask import Blueprint, request

#extensions
from app.models.main import Company, Container, Storage, Stock
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import func

#utils
from app.utils.helpers import JSONResponse, ErrorMessages
from app.utils.route_helper import get_pagination_params, pagination_form
from app.utils.route_decorators import json_required, role_required
from app.utils.db_operations import (
    update_row_content, handle_db_error
)
from app.utils.exceptions import APIException
from app.utils.validations import validate_id


storages_bp = Blueprint('storages_bp', __name__)


@storages_bp.route('/', methods=['GET'])
@storages_bp.route('/<int:storage_id>', methods=['GET'])
@json_required()
@role_required()
def get_storages(role, storage_id=None):

    if storage_id == None:
        page, limit = get_pagination_params()
        store = role.company.storages.order_by(Storage.name.asc()).paginate(page, limit) #return all storages,
        return JSONResponse(
            message="ok",
            payload={
                "storages": list(map(lambda x: x.serialize(), store.items)),
                **pagination_form(store)
            }
        ).to_json()

    #if an id has been passed in as a request arg.
    storage = role.company.get_storage_by_id(storage_id)
    if storage is None:
        raise APIException.from_error(ErrorMessages(parameters='storage_id').notFound)

    #?return storage
    return JSONResponse(
        message="ok",
        payload={
            "storage": storage.serialize_all()
        }
    ).to_json()


@storages_bp.route('/', methods=['POST'])
@json_required({'name': str})
@role_required()
def create_storage(role, body):

    new_name = body['name'].lower()
    error = ErrorMessages(parameters='name')

    name_exists = db.session.query(Storage).select_from(Company).join(Company.storages).\
        filter(func.lower(Storage.name) == new_name, Company.id == role.company.id).first()

    if name_exists:
        error.custom_msg = f'<name:{new_name}> already exists'
        raise APIException.from_error(error.conflict)

    new_values, invalids, msg = update_row_content(Storage, body)
    if invalids:
        error.parameters.append(invalids)
        error.custom_msg = msg
        raise APIException.from_error(error.bad_request)

    if request.method == 'POST':
        new_values["_company_id"] = role.company.id # add current user company_id to dict
        new_item = Storage(**new_values)

        try:
            db.session.add(new_item)
            db.session.commit()
        except SQLAlchemyError as e:
            handle_db_error(e)

        return JSONResponse(
            payload={'storage': new_item.serialize()}, status_code=201
        ).to_json()

    #request.method == 'PUT'

@storages_bp.route('/<int:storage_id>', methods=['PUT'])
@json_required({'name': str})
@role_required(level=1)
def update_storage(role, body, storage_id):

    error = ErrorMessages(parameters='storage_id')
    target_storage = role.company.get_storage_by_id(storage_id)
    new_name = body['name'].lower()

    if not target_storage:
        raise APIException.from_error(error.notFound)

    name_exists = db.session.query(Storage).select_from(Company).join(Company.storages).\
        filter(func.lower(Storage.name) == new_name, Company.id == role.company.id, Storage.id != target_storage.id).first()

    if name_exists:
        error.custom_msg = f'storage_name: {new_name} already exists'
        raise APIException.from_error(error.conflict)

    new_values, invalids, msg = update_row_content(Storage, body)
    if invalids:
        error.parameters.append(invalids)
        error.custom_msg = msg
        raise APIException.from_error(error.bad_request)

    try:
        Storage.query.filter(Storage.id == storage_id).update(new_values)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f'Storage-id-{storage_id} updated').to_json()


@storages_bp.route('/<int:storage_id>', methods=['DELETE'])
@json_required()
@role_required()
def delete_storage(role, storage_id):

    error = ErrorMessages(parameters='storage_id')
    storage = role.company.get_storage_by_id(storage_id)
    if storage is None:
        raise APIException.from_error(error.notFound)

    try:
        db.session.delete(storage)
        db.session.commit()
    except IntegrityError as ie:
        error.custom_msg = f"can't delete storage_id:{storage_id} - {ie}"
        raise APIException.from_error(error.conflict)
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f"storage id: <{storage_id}> has been deleted").to_json()

#GET endpoint for itms in stock is not present here because will be used the GET endpoint in items.py blueprint.

@storages_bp.route('/<int:storage_id>/items', methods=['POST'])
@json_required({"item_id": int})
@role_required(level=1)
def crate_item_stock(role, body, storage_id):

    error = ErrorMessages()
    item_id = body['item_id']
    item = role.company.get_item_by_id(item_id)
    if item is None:
        error.parameters.append('item_id')

    storage = role.company.get_storage_by_id(storage_id)
    if storage is None:
        error.parameters.append('storage_id')

    if error.parameters != []:
        raise APIException.from_error(error.notFound)

    stock = Stock.get_stock(item_id=item.id, storage_id=storage.id)
    if stock is not None:
        error.parameters.append('item_id')
        error.custom_msg = f"item id:<{item_id}> already exists in current storage"
        raise APIException.from_error(error.conflict)

    to_add, invalids, msg = update_row_content(Stock, body)
    if invalids:
        raise APIException.from_error(ErrorMessages(parameters=invalids, custom_msg=msg).bad_request)
    
    to_add.update({'_item_id': item_id, '_storage_id': storage.id})

    new_stock = Stock(**to_add)

    try:
        db.session.add(new_stock)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        payload={
            'item': item.serialize_all(),
            'stock': new_stock.serialize()
        },
        status_code=201
    ).to_json()


#7
@storages_bp.route('/<int:storage_id>/items/<int:item_id>', methods=['PUT'])
@json_required()
@role_required(level=1)
def update_stock_in_storage(role, body, storage_id, item_id):

    error = ErrorMessages()
    storage = role.company.get_storage_by_id(storage_id)
    item = role.company.get_item_by_id(item_id)

    if storage is None:
        error.parameters.append('storage_id')

    if item is None:
        error.parameters.append('item_id')

    if error.parameters != []:
        raise APIException.from_error(error.notFound)

    target_stock = Stock.get_stock(item_id=item.id, storage_id=storage.id)
    if target_stock is None:
        error.parameters.append('stock')
        error.custom_msg = f'relation between storage_id:{storage_id} and item_id:{item_id} does not exists'
        raise APIException.from_error(error.notFound)

    to_update, invalids, msg = update_row_content(Stock, body)
    if invalids:
        error.parameters.append(invalids)
        error.custom_msg = msg
        raise APIException.from_error(error.bad_request)

    try:
        db.session.query(Stock).filter(Stock.id == target_stock.id).update(to_update)
        db.session.commit()

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f'stock updated').to_json()


#8
@storages_bp.route('/<int:storage_id>/containers', methods=['GET'])
@json_required()
@role_required()
def get_storage_containers(role, storage_id):

    error = ErrorMessages()
    storage = role.company.get_storage_by_id(storage_id)
    page, limit = get_pagination_params()

    if storage is None:
        error.parameters.append('storage_id')
        raise APIException.from_error(error.notFound)

    containers = storage.containers.paginate(page, limit)

    return JSONResponse(payload={
        'containers': list(map(lambda x:x.serialize(), containers.items)),
        **pagination_form(containers)
    }).to_json()


#9
@storages_bp.route('/<int:storage_id>/containers', methods=['POST'])
@json_required()
@role_required(level=1)
def create_container(role, body, storage_id):

    error = ErrorMessages()
    storage = role.company.get_storage_by_id(storage_id)

    if not storage:
        error.parameters.append('storage_id')
        raise APIException.from_error(error.notFound)

    to_add, invalids, msg = update_row_content(Container, body)
    if invalids:
        error.parameters.append(invalids)
        error.custom_msg = msg
        raise APIException.from_error(error.bad_request)

    to_add.update({'_storage_id': storage.id})

    new_container = Container(**to_add)

    try:
        db.session.add(new_container)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message=f'new container created',
        payload={
            'container': new_container.serialize_all()
        }
    ).to_json()


#10
@storages_bp.route('/containers/<int:container_id>', methods=['PUT'])
@json_required()
@role_required(level=1)
def update_container(role, body, container_id):

    error = ErrorMessages()

    valid_id = validate_id(container_id)
    if not valid_id:
        raise APIException.from_error(error.bad_request)

    target_container = db.session.query(Container).select_from(Company).join(Company.storages).\
        join(Storage.containers).filter(Company.id == role.company.id, Container.id == container_id).first()

    if not target_container:
        error.parameters.append('container_id')

    if error.parameters:
        raise APIException.from_error(error.notFound)

    to_update, invalids, msg = update_row_content(Container, body)
    if invalids:
        error.parameters.append(invalids)
        error.custom_msg = msg
        raise APIException.from_error(error.bad_request)

    try:
        db.session.query(Container).filter(Container.id == target_container.id).update(to_update)
        db.session.commit()

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(message=f'container_id:{container_id} updated').to_json()


@storages_bp.route('/containers/<int:container_id>', methods=['DELETE'])
@json_required()
@role_required(level=1)
def delete_container(role, container_id):

    error = ErrorMessages(parameters='container_id')

    valid_id = validate_id(container_id)
    if not valid_id:
        raise APIException.from_error(error.bad_request)

    target_container = db.session.query(Container).select_from(Company).join(Company.storages).\
        join(Storage.containers).filter(Company.id == role.company.id, container_id == container_id).first()

    if not target_container:
        raise APIException.from_error(error.notFound)

    try:
        db.session.delete(target_container)
        db.session.commit()

    except IntegrityError as ie:
        error.custom_msg = f"can't delete container_id:{container_id} - {ie}"
        raise APIException.from_error(error.conflict)

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message=f'container_id:{container_id} was deleted'
    ).to_json()