from flask import Blueprint, request

#extensions
from app.models.main import Company, Container, QRCode, Storage
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import func

#utils
from app.utils.helpers import JSONResponse, ErrorMessages as EM, QueryParams, StringHelpers, IntegerHelpers
from app.utils.route_decorators import json_required, role_required
from app.utils.db_operations import (
    update_row_content, handle_db_error, Unaccent
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
    qp = QueryParams(request.args)
    if storage_id is None:
        page, limit = qp.get_pagination_params()
        storageInstancesList = role.company.storages.order_by(Storage.name.asc()).paginate(page, limit) #return all storages,
        return JSONResponse(
            message=qp.get_warings(),
            payload={
                "storages": list(map(lambda x: x.serialize(), storageInstancesList.items)),
                **qp.get_pagination_form(storageInstancesList)
            }
        ).to_json()

    #if an id has been passed in as a request arg.
    valid, msg = IntegerHelpers.is_valid_id(storage_id)
    if not valid:
        raise APIException.from_error(EM({"storage_id": msg}).bad_request)

    storageInstace = role.company.get_storage_by_id(storage_id)
    if not storageInstace:
        raise APIException.from_error(EM({"storage_id": f"id-{storage_id} not found"}).notFound)

    #?return storage
    return JSONResponse(
        message=qp.get_warings(),
        payload={
            "storage": storageInstace.serialize_all()
        }
    ).to_json()


@storages_bp.route('/', methods=['POST'])
@json_required({'name': str})
@role_required()
def create_storage(role, body):

    newRows, invalids = update_row_content(Storage, body)
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    newName = StringHelpers(body["name"])
    sameNameInstance = db.session.query(Storage).select_from(Company).join(Company.storages).\
        filter(Unaccent(func.lower(Storage.name)) == newName.no_accents.lower(), Company.id == role.company.id).first()

    if sameNameInstance:
        raise APIException.from_error(EM({"name": f"<name:{newName.value}> already exists"}).conflict)

    newRows["company_id"] = role.company.id # add current user company_id to dict
    new_item = Storage(**newRows)

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

    newName = StringHelpers(body["name"])
    newRows, invalids = update_row_content(Storage, body)
    valid, msg = IntegerHelpers.is_valid_id(storage_id)
    if not valid:
        invalids.update({"storage_id": msg})

    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    targetStorage = role.comany.get_storage_by_id(storage_id)
    if not targetStorage:
        raise APIException.from_error(EM({"storage_id": f"id-{storage_id} not found"}).notFound)

    sameNameInstance = db.session.query(Storage).select_from(Company).join(Company.storages).\
        filter(Unaccent(func.lower(Storage.name)) == newName.no_accents.lower(), \
            Company.id == role.company.id, Storage.id != targetStorage.id).first()

    if sameNameInstance:
        raise APIException.from_error(EM({"name": f"storage_name: {newName.value} already exists"}).conflict)

    try:
        Storage.query.filter(Storage.id == storage_id).update(newRows)
        db.session.commit()

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f'Storage-id-{storage_id} updated').to_json()


@storages_bp.route('/<int:storage_id>', methods=['DELETE'])
@json_required()
@role_required()
def delete_storage(role, storage_id):

    valid, msg = IntegerHelpers.is_valid_id(storage_id)
    if not valid:
        raise APIException.from_error(EM({"storage_id": msg}).bad_request)

    targetStorage = role.company.get_storage_by_id(storage_id)
    if not targetStorage:
        raise APIException.from_error(EM({"storage_id": f"id-{storage_id} not found"}).notFound)

    try:
        db.session.delete(targetStorage)
        db.session.commit()

    except IntegrityError as ie:
        raise APIException.from_error(EM({"storage_id": f"can't delete storage_id:{storage_id} - {ie}"}).conflict)
        
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
    qp = QueryParams(request.args)
    valid, msg = IntegerHelpers.is_valid_id(storage_id)
    if not valid:
        raise APIException.from_error(EM({"storage_id": msg}).bad_request)

    targetStorage = role.company.get_storage_by_id(storage_id)
    
    if not targetStorage:
        raise APIException.from_error(EM({"storage_id": f"id-{storage_id} not found"}).notFound)

    containerID = qp.get_first_value("cid", as_integer=True)
    if containerID:
        valid, msg = IntegerHelpers.is_valid_id(containerID)
        if not valid:
            raise APIException.from_error(EM({"container_id": msg}).bad_request)

        targetContainer = targetStorage.containers.filter(Container.id == containerID).first()
        if not targetContainer:
            raise APIException.from_error(EM({"container_id": f"id-{containerID} not found"}).notFound)

        return JSONResponse(
            message=qp.get_warings(),
            payload={
                "container": targetContainer.serialize_all()
            }
        ).to_json()

    qrCode = qp.get_first_value("qr_code")
    if qrCode:
        qrCodeID = QRCode.parse_qr(qrCode)
        if not qrCodeID:
            raise APIException.from_error(EM({"qr_code": "invalid qrcode"}).notAcceptable)

        targetContainer = targetStorage.containers.filter(QRCode.id == qrCodeID).first()
        if not targetContainer:
            raise APIException.from_error(EM({"qr_code": f"id-{qrCodeID} not found"}).notFound)

        if not targetContainer.qr_code.is_active:
            raise APIException.from_error(EM({"qr_code": "qr_code has been disabled"}).unauthorized)

        return JSONResponse(
            message=qp.get_warings(),
            payload={
                "container": targetContainer.serialize_all()
            }
        ).to_json()
    
    page, limit = qp.get_pagination_params()
    containers = targetStorage.containers.paginate(page, limit)

    return JSONResponse(
        message=qp.get_warings(),
        payload={
            'containers': list(map(lambda x:x.serialize(), containers.items)),
            **qp.get_pagination_form(containers)
    }).to_json()


@storages_bp.route('/<int:storage_id>/containers', methods=['POST'])
@json_required()
@role_required(level=1)
def create_container(role, body, storage_id):

    newRows, invalids = update_row_content(Container, body)
    valid, msg = IntegerHelpers.is_valid_id(storage_id)
    if not valid:
        invalids.update({"storage_id": msg})
    
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    targetStorage = role.company.get_storage_by_id(storage_id)

    if not targetStorage:
        raise APIException.from_error(EM({"storage_id": f"id-{storage_id} not found"}).notFound)

    newRows.update({'storage_id': targetStorage.id})
    newQRCode = QRCode(company_id = role.company.id)
    newContainer = Container(**newRows, qr_code=newQRCode)

    try:
        db.session.add_all([newQRCode, newContainer])
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message=f'new container created',
        payload={
            'container': newContainer.serialize_all()
        }
    ).to_json()


@storages_bp.route('/containers/<int:container_id>', methods=['PUT'])
@json_required()
@role_required(level=1)
def update_container(role, body, container_id):

    newRows, invalids = update_row_content(Container, body)
    valid, msg = IntegerHelpers.is_valid_id(container_id)
    if not valid:
        invalids.update({"container_id": msg})

    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    targetContainer = db.session.query(Container).select_from(Company).join(Company.storages).\
        join(Storage.containers).filter(Company.id == role.company.id, Container.id == container_id).first()

    if not targetContainer:
        raise APIException.from_error(EM({"container_id": f"id-{container_id} not found"}))

    try:
        db.session.query(Container).filter(Container.id == targetContainer.id).update(newRows)
        db.session.commit()

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(message=f'container_id:{container_id} updated').to_json()


@storages_bp.route('/containers/<int:container_id>', methods=['DELETE'])
@json_required()
@role_required(level=1)
def delete_container(role, container_id):

    valid, msg = IntegerHelpers.is_valid_id(container_id)
    if not valid:
        raise APIException.from_error(EM({"container_id": msg}).bad_request)

    targetContainer = db.session.query(Container).select_from(Company).join(Company.storages).\
        join(Storage.containers).filter(Company.id == role.company.id, container_id == container_id).first()

    if not targetContainer:
        raise APIException.from_error(EM({"container_id": f"id-{container_id} not found"}).notFound)

    try:
        db.session.delete(targetContainer)
        db.session.commit()

    except IntegrityError as ie:
        raise APIException.from_error(EM({
            "container_id": f"can't delete container_id:{container_id} - {ie}"
        }).conflict)

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message=f'container_id:{container_id} was deleted'
    ).to_json()


@storages_bp.route("/containers/<int:container_id>/qrcode", methods=["PUT"])
@json_required({"qr_code": str})
@role_required()
def assign_qrcode(role, body, container_id):

    qrcode = body["qr_code"]
    valid, msg = IntegerHelpers.is_valid_id(container_id)
    if not valid:
        raise APIException.from_error(EM({"container_id": msg}).bad_request)

    qrCodeID = QRCode.parse_qr(qrcode)
    if not qrCodeID:
        raise APIException.from_error(EM({"qr_code": "invalid qrcode in request"}).notAcceptable)

    qrCodeInstance = db.session.query(QRCode).join(QRCode.company).\
        filter(QRCode.id == qrCodeID, Company.id == role.company.id).first()
        
    if not qrCodeInstance or not qrCodeInstance.is_active:
        raise APIException.from_error(EM({"qr_code": f"qr_code_id not found"}).notFound)

    if qrCodeInstance.is_used:
        raise APIException.from_error(EM({"qr_code": "qrcode is already in use.."}).conflict)

    targetContainer = db.session.query(Container).join(Container.storage).join(Storage.company).\
        filter(Company.id == role.company.id, Container.id == container_id).first()

    if not targetContainer:
        raise APIException.from_error(EM({"container_id": f"id-{container_id} not found"}).notFound)

    try:
        targetContainer.qr_code = qrCodeInstance
        db.session.commit()

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message="qrcode assigned to container"
    ).to_json()