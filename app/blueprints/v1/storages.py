from flask import Blueprint, request

#extensions
from app.models.main import Acquisition, Company, Container, Inventory, QRCode, Storage
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import func

#utils
from app.utils.helpers import JSONResponse, ErrorMessages as EM, QueryParams, StringHelpers, IntegerHelpers, Validations
from app.utils.route_decorators import json_required, role_required
from app.utils.db_operations import (
    ContainerValidations, update_row_content, handle_db_error, Unaccent
)
from app.utils.exceptions import APIException


storages_bp = Blueprint('storages_bp', __name__)


@storages_bp.route('/', methods=['GET'])
@json_required()
@role_required()
def get_storages(role):
    """
    query parameters:
    ?page:<int> - pagination page, default=1
    ?limit:<int> - pagination limit, default=20
    ?storage_id:<int> - id of required storage
    """
    qp = QueryParams(request.args)
    storage_id = qp.get_first_value("storage_id", as_integer=True)

    if not storage_id:
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
    nameExists = db.session.query(Storage).select_from(Company).join(Company.storages).\
        filter(Unaccent(func.lower(Storage.name)) == newName.unaccent.lower(), Company.id == role.company.id).first()

    if nameExists:
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

    targetStorage = role.company.get_storage_by_id(storage_id)
    if not targetStorage:
        raise APIException.from_error(EM({"storage_id": f"id-{storage_id} not found"}).notFound)

    sameName = db.session.query(Storage).select_from(Company).join(Company.storages).\
        filter(Unaccent(func.lower(Storage.name)) == newName.unaccent.lower(), \
            Company.id == role.company.id, Storage.id != targetStorage.id).first()

    if sameName:
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
    ?container_id:<int> - filter by container_id
    ?qr_code:<int> - filter by qr_code_id
    """
    qp = QueryParams(request.args)
    valid, msg = IntegerHelpers.is_valid_id(storage_id)
    if not valid:
        raise APIException.from_error(EM({"storage_id": msg}).bad_request)

    targetStorage = role.company.get_storage_by_id(storage_id)
    
    if not targetStorage:
        raise APIException.from_error(EM({"storage_id": f"id-{storage_id} not found"}).notFound)

    containerID = qp.get_first_value("container_id", as_integer=True)
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

        targetContainer = targetStorage.containers.filter(Container.qr_code_id == qrCodeID).first()
        if not targetContainer:
            raise APIException.from_error(EM({"container_id": f"id-{qrCodeID} not found"}).notFound)

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

    targetStorage = db.session.query(Storage.id).filter(Storage.company_id == role.company.id).\
        filter(Storage.id == storage_id).first()

    if not targetStorage:
        raise APIException.from_error(EM({"storage_id": f"id-{storage_id} not found"}).notFound)

    newRows.update({'storage_id': storage_id})
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
        },
        status_code=201
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


@storages_bp.route('/containers', methods=['DELETE'])
@json_required()
@role_required(level=1)
def delete_container(role):

    qp = QueryParams(request.args)
    target_container_id = qp.get_first_value("container", as_integer=True)
    if not target_container_id:
        raise APIException.from_error(EM({"container_id": qp.get_warings()}).bad_request)

    targetContainer = db.session.query(Container.id).select_from(Company).join(Company.storages).\
        join(Storage.containers).filter(Company.id == role.company.id, Container.id == target_container_id).first()

    if not targetContainer:
        raise APIException.from_error(EM({"container_id": f"id-{target_container_id} not found"}).notFound)

    try:
        db.session.delete(targetContainer)
        db.session.commit()

    except IntegrityError as ie:
        raise APIException.from_error(EM({
            "container_id": f"can't delete container:{target_container_id} - {ie}"
        }).conflict)

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message=f'container_id:{target_container_id} has been deleted'
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


@storages_bp.route("/<int:storage_id>/acquisitions", methods=["GET"])
@json_required()
@role_required(level=2)
def get_storage_acquisitions(role, storage_id):

    valid, msg = IntegerHelpers.is_valid_id(storage_id)
    if not valid:
        raise APIException.from_error(EM({"storage_id": msg}).bad_request)

    target_storage = db.session.query(Storage).\
        filter(Storage.company_id == role.company.id, Storage.id == storage_id).first()

    if not target_storage:
        raise APIException.from_error(EM({"storage_id": f"ID-{storage_id} not found"}).notFound)

    base_q = db.session.query(Acquisition).select_from(Company).join(Company.storages).join(Storage.acquisitions).\
        filter(Company.id == role.company.id, Storage.id == storage_id)

    qp = QueryParams(request.args)
    acq_id = qp.get_first_value("acquisition_id", as_integer=True)
    if not acq_id:

        # add filters here
        
        page, limit = qp.get_pagination_params()
        result = base_q.paginate(page, limit)

        return JSONResponse(
            message=qp.get_warings(),
            payload={
                "storge": target_storage.serialize(),
                "acquisitions": list(map(lambda x:x.serialize(), result.items)),
                **qp.get_pagination_form(result)
            }
        ).to_json()

    #if acq_id in query parameters:
    valid, msg = IntegerHelpers.is_valid_id(acq_id)
    if not valid:
        raise APIException.from_error(EM({"acquisition_id": msg}).bad_request)

    target_acq = base_q.filter(Acquisition.id == acq_id).first()
    if not target_acq:
        raise APIException.from_error(EM({"acquisition_id": f"ID-{acq_id} not found"}).notFound)

    return JSONResponse(
        message=f"acquisition-{acq_id} storage-{storage_id}",
        payload={
            "acquisition": target_acq.serialize_all()
        }
    ).to_json()


@storages_bp.route("/acquisitions/<int:acq_id>/inventories", methods=["GET"])
@json_required()
@role_required(level=2)
def get_acq_inventories(role, acq_id):

    valid, msg = IntegerHelpers.is_valid_id(acq_id)
    if not valid:
        raise APIException.from_error(EM({"acquisition_id": msg}).bad_request)

    target_acq = db.session.query(Acquisition).select_from(Company).join(Company.storages).join(Storage.acquisitions).\
        filter(Acquisition.id == acq_id, Company.id == role.company.id).first()

    if not target_acq:
        raise APIException.from_error(EM({"acquisition_id": f"ID-{acq_id} not found"}).notFound)

    base_q = db.session.query(Inventory).select_from(Company).join(Company.storages).join(Storage.acquisitions).\
        join(Acquisition.inventories).filter(Company.id == role.company.id, Acquisition.id == acq_id)

    qp = QueryParams(request.args)
    inventory_id = qp.get_first_value("inventory_id", as_integer=True)
    if not inventory_id:

        #add filters herer

        page, limit = qp.get_pagination_params()
        result = base_q.paginate(page, limit)

        return JSONResponse(
            message=qp.get_warings(),
            payload={
                "acquisition": target_acq.serialize(),
                "inventories": list(map(lambda x:x.serialize(), result.items)),
                **qp.get_pagination_form(result)
            }
        ).to_json()

    #if inventory_id in request args:
    valid, msg = IntegerHelpers.is_valid_id(inventory_id)
    if not valid:
        raise APIException.from_error(EM({"inventory_id": msg}).bad_request)

    target_inv = base_q.filter(Inventory.id == inventory_id).first()
    if not target_inv:
        raise APIException.from_error(EM({"inventory_id": f"ID-{inventory_id} not found"}).notFound)

    return JSONResponse(
        message=f"acquisition-{acq_id} inventory-{inventory_id}",
        payload={
            "inventory": target_inv.serialize_all()
        }
    ).to_json()


@storages_bp.route("/acquisitions/<int:acq_id>/inventories", methods=["POST"])
@json_required({"container_id": int})
@role_required(level=2)
def create_inventory(role, body, acq_id):

    container_id = body["container_id"]
    invalids = Validations.validate_inputs({
        "container_id": IntegerHelpers.is_valid_id(container_id),
        "acquisition_id": IntegerHelpers.is_valid_id(acq_id)
    })

    newRows, invalid_body = update_row_content(Inventory, body)
    invalids.update(invalid_body)
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)
    
    target_acquisition = db.session.query(Acquisition.id).select_from(Company).join(Company.storages).\
        join(Storage.acquisitions).filter(Company.id == role.company.id, Acquisition.id == acq_id).first()

    if not target_acquisition:
        raise APIException.from_error(EM({"acquisition_id": f"ID-{acq_id} not found"}).notFound)

    container = ContainerValidations(role.company.id, container_id)
    if not container.is_found:
        raise APIException.from_error(EM({"container_id": container.not_found_message}).notFound)

    #ensure to hold same items per container.
    if not container.sameItemContained(target_acquisition.item_id):
        raise APIException.from_error(EM({"container_id": container.conflict_message}).conflict)

    newRows.update({
        "acquisition_id": acq_id,
        "container_id": container_id
    })

    newInventory = Inventory(**newRows)
    try:
        db.session.add(newInventory)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message="new inventory created",
        payload={
            "inventory": newInventory.serialize_all()
        },
        status_code=201
    ).to_json()


@storages_bp.route("/acquisitions/inventories/<int:inventory_id>", methods=["PUT", "DELETE"])
@json_required()
@role_required(level=2)
def update_or_delete_inventory(role, inventory_id, body=None):

    invalids = Validations.validate_inputs({
        "inventory_id": inventory_id
    })
    if body:
        newRows, invalid_body = update_row_content(Inventory, body)
        invalids.update(invalid_body)

    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    target_inventory = db.session.query(Inventory).select_from(Company).join(Company.storages).\
        join(Storage.containers).join(Container.inventories).\
            filter(Company.id == role.company.id, Inventory.id == inventory_id).first()

    if not target_inventory:
        raise APIException.from_error(EM({"inventory_id": f"ID-{inventory_id} not found"}).notFound)

    if request.method == "DELETE":
        try:
            db.session.delete(target_inventory)
            db.session.commit()
        except IntegrityError as ie:
            raise APIException.from_error(EM({"inventory_id": f"can't delete inventory_id-{inventory_id}, {ie}"}).conflict)

        except SQLAlchemyError as e:
            handle_db_error(e)

        return JSONResponse(message="inventory deleted").to_json()

    #if request.method=="PUT"
    if "container_id" in body:
        container = ContainerValidations(role.company.id, body["container_id"])
        if not container.is_found:
            raise APIException.from_error(EM({"container_id": container.not_found_message}).notFound)

        if not container.sameItemContained(target_inventory.acquisition.item_id):
            raise APIException.from_error(EM({"container_id": container.conflict_message}).conflict)

        newRows.update({
            "container_id": container.container_id
        })

    try:
        db.session.query(Inventory).filter(Inventory.id == inventory_id).update(newRows)
        db.session.commit()

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message="inventory updated",
    ).to_json()