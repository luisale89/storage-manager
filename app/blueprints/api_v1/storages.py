from flask import Blueprint, request

#extensions
from app.models.main import Company, Container, QRCode, Storage
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import func

#utils
from app.utils.helpers import JSONResponse, ErrorMessages, QueryParams
from app.utils.route_decorators import json_required, role_required
from app.utils.db_operations import (
    update_row_content, handle_db_error
)
from app.utils.exceptions import APIException


storages_bp = Blueprint('storages_bp', __name__)


@storages_bp.route('/', methods=['GET'])
@storages_bp.route('/<int:storage_id>', methods=['GET'])
@json_required()
@role_required()
def get_storages(role, storage_id=None):
    """
    query parameters:
    ?page:<int> - pagination page, default=1
    ?limit:<int> - pagination limit, default=20
    """
    qp = QueryParams()
    if storage_id is None:
        page, limit = qp.get_pagination_params()
        store = role.company.storages.order_by(Storage.name.asc()).paginate(page, limit) #return all storages,
        return JSONResponse(
            message="ok",
            payload={
                "storages": list(map(lambda x: x.serialize(), store.items)),
                **qp.get_pagination_form(store)
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
        new_values["company_id"] = role.company.id # add current user company_id to dict
        new_item = Storage(**new_values)

        try:
            db.session.add(new_item)
            db.session.commit()

        except SQLAlchemyError as e:
            handle_db_error(e)

        return JSONResponse(
            payload={'storage': new_item.serialize()}, status_code=201
        ).to_json()


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


@storages_bp.route('/<int:storage_id>/containers', methods=['GET'])
@json_required()
@role_required()
def get_storage_containers(role, storage_id):
    """
    query paramters
    ?page:<int> - pagination page, default:1
    ?limit:<int> - pagination limit, default:20
    ?cid:<int> - filter by container_id
    ?qr_code:<int> - filter by qr_code_id
    """
    qp = QueryParams()
    error = ErrorMessages()
    storage = role.company.get_storage_by_id(storage_id)
    
    if storage is None:
        error.parameters.append('storage_id')
        raise APIException.from_error(error.notFound)

    container_id = request.args.get("cid", None)
    if container_id:
        valid_cont_id = validate_id(container_id)
        if not valid_cont_id:
            error.parameters.append("container_id")
            raise APIException.from_error(error.bad_request)

        target_container = storage.containers.filter(Container.id == valid_cont_id).first()
        if not target_container:
            error.parameters.append("container_id")
            raise APIException.from_error(error.notFound)

        return JSONResponse(
            message="ok",
            payload={
                "container": target_container.serialize_all()
            }
        ).to_json()

    qr_code = request.args.get("qr_code", None)
    if qr_code:
        qr_code_id = QRCode.parse_qr(qr_code)
        if not qr_code_id:
            error.parameters.append("qr_code")
            raise APIException.from_error(error.notAcceptable)

        target_container = storage.containers.filter(QRCode.id == qr_code_id).first()
        if not target_container:
            error.parameters.append("container")
            raise APIException.from_error(error.notFound)

        if not target_container.qr_code.is_active:
            error.parameters.append("qr_code")
            raise APIException.from_error(error.unauthorized)

        return JSONResponse(
            message="ok",
            payload={
                "container": target_container.serialize_all()
            }
        ).to_json()
    
    page, limit = qp.get_pagination_params()
    containers = storage.containers.paginate(page, limit)

    return JSONResponse(payload={
        'containers': list(map(lambda x:x.serialize(), containers.items)),
        **qp.get_pagination_form(containers)
    }).to_json()


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

    new_qr_code = QRCode(
        company_id = role.company.id
    )

    to_add.update({
        'storage_id': storage.id
    })

    new_container = Container(**to_add, qr_code=new_qr_code)

    try:
        db.session.add_all([new_qr_code, new_container])
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message=f'new container created',
        payload={
            'container': new_container.serialize_all()
        }
    ).to_json()


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


@storages_bp.route("/containers/<int:container_id>/qrcode", methods=["PUT"])
@json_required({"qr_code": str})
@role_required()
def assign_qrcode(role, body, container_id):

    error = ErrorMessages()
    qrcode = body["qr_code"]

    qrcode_id = QRCode.parse_qr(qrcode)
    if not qrcode_id:
        error.parameters.append("qr_code")
        error.custom_msg = "invalid qrcode in request"
        raise APIException.from_error(error.notAcceptable)

    qrcode_instance = db.session.query(QRCode).join(QRCode.company).\
        filter(QRCode.id == qrcode_id, Company.id == role.company.id).first()
        
    if not qrcode_instance or not qrcode_instance.is_active:
        error.parameters.append("qr_code")
        raise APIException.from_error(error.notFound)

    if qrcode_instance.is_used:
        error.parameters.append("qr_code")
        error.custom_msg = "qrcode is already in use.."
        raise APIException.from_error(error.conflict)

    target_container = db.session.query(Container).join(Container.storage).join(Storage.company).\
        filter(Company.id == role.company.id, Container.id == container_id).first()

    if not target_container:
        error.parameters.append("container_id")
        raise APIException.from_error(error.notFound)

    try:
        target_container.qr_code = qrcode_instance
        db.session.commit()

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message="qrcode assigned to container"
    ).to_json()