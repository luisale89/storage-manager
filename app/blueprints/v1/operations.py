from flask import Blueprint, request

#models
from app.models.main import Acquisition, Company, Item, Order, OrderRequest, Provider, Storage, SupplyRequest
from app.extensions import db
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import ErrorMessages as EM, IntegerHelpers, JSONResponse, QueryParams, Validations
from app.utils.route_decorators import json_required, role_required
from app.utils.db_operations import handle_db_error, update_row_content

operations_bp = Blueprint("operations_bp", __name__)

# prefix: operations/
# endpoints:

@operations_bp.route("/supply-requests", methods=["GET"])
@json_required()
@role_required(level=1)
def get_supply_requests(role):

    qp = QueryParams(request.args)
    q = db.session.query(SupplyRequest).select_from(Company).join(Company.supply_requests).\
        filter(Company.id == role.company.id)
    
    sr_id = qp.get_first_value("id", as_integer=True)
    if not sr_id:

        # add filters here...

        page, limit = qp.get_pagination_params()
        sr_instances = q.paginate(page, limit)

        return JSONResponse(
            message=qp.get_warings(),
            payload={
                "supply_requests": list(map(lambda x:x.serialize(), sr_instances.items)),
                **qp.get_pagination_form(sr_instances)
            }
        ).to_json()

    #supply_request_id in query
    valid, msg = IntegerHelpers.is_valid_id(sr_id)
    if not valid:
        raise APIException.from_error(EM({"supply_request_id": msg}).bad_request)

    target_instance = q.filter(SupplyRequest.id == sr_id).first()
    if not target_instance:
        raise APIException.from_error(EM({"supply_request_id": f"ID-{sr_id} not found"}).notFound)

    return JSONResponse(
        message="return supply-request data",
        payload={
            "supply_request": target_instance.serialize_all()
        }
    ).to_json()


@operations_bp.route("/supply-requests", methods=["POST"])
@json_required({"storage_id": int})
@role_required(level=1)
def create_supply_request(role, body):

    storage_id = body["storage_id"]
    valid, msg = IntegerHelpers.is_valid_id(storage_id)
    if not valid:
        raise APIException.from_error(EM({"storage_id", msg}).bad_request)

    target_storage = db.session.query(Storage).select_from(Company).join(Company.storages).\
        filter(Company.id == role.company.id, Storage.id == storage_id).first()
    if not target_storage:
        raise APIException.from_error(EM({"storage_id", f"ID-{storage_id} not found"}).notFound)

    newRows, invalids = update_row_content(SupplyRequest, body)
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    newRows.update({
        "company_id": role.company.id,
        "storage_id": storage_id
    })

    newSupplyReq = SupplyRequest(**newRows)

    try:
        db.session.add(newSupplyReq)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message="new supply_request created",
        payload={
            "supply_request": newSupplyReq.serialize_all()
        },
        status_code=201
    ).to_json()


@operations_bp.route("/supply-requests/<int:sr_id>", merhods=["PUT", "DELETE"])
@json_required()
@role_required(level=1)
def update_supply_request(role, sr_id, body=None):

    valid, msg = IntegerHelpers.is_valid_id(sr_id)
    if not valid:
        raise APIException.from_error(EM({"supply_request_id": msg}).bad_request)

    target_srq = db.session.query(SupplyRequest).filter(SupplyRequest.company_id == role.company.id).\
        filter(SupplyRequest.id == sr_id).first()
    if not target_srq:
        raise APIException.from_error(EM({"supply_request_id": f"ID-{sr_id} not found"}).notFound)

    if request.method == "DELETE":

        try:
            db.session.delete(target_srq)
            db.session.commit()

        except IntegrityError as ie:
            raise APIException.from_error(EM(
                {"supply_request_id": f"can't delete supply_request_id-{sr_id} - {ie}"}
            ).conflict)

        except SQLAlchemyError as e:
            handle_db_error(e)

        return JSONResponse(
            message=f"supply_request_id-{sr_id} deleted"
        ).to_json()

    #request.method == 'PUT'
    newRows, invalids = update_row_content(SupplyRequest, body)
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    try:
        db.session.query(SupplyRequest.id == sr_id).update(newRows)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message="supply_request updated"
    ).to_json()


@operations_bp.route("/supply-requests/<int:sr_id>/acquisitions", methods=["GET"])
@json_required()
@role_required(level=1)
def get_sr_acquisitions(role, sr_id):

    qp = QueryParams(request.args)
    valid, msg = IntegerHelpers.is_valid_id(sr_id)
    if not valid:
        raise APIException.from_error(EM({"supply_request_id": msg}).bad_request)

    target_supply_instance = db.sesion.query(SupplyRequest.id).select_from(Company).join(Company.supply_requests).\
        filter(Company.id == role.company.id).first()
    
    if not target_supply_instance:
        raise APIException.from_error(EM({"supply_request_id": f"ID-{sr_id} not found"}).notFound)

    q = db.session.query(Acquisition).select_from(Company).join(Company.supply_requests).\
        join(SupplyRequest.acquisitions).filter(Company.id == role.company.id, SupplyRequest.id == sr_id)

    acq_id = qp.get_first_value("id", as_integer=True)
    if not acq_id:

        # add filters here

        page, limit = qp.get_pagination_params()
        acq_instances = q.paginate(page, limit)

        return JSONResponse(
            message=qp.get_warings(),
            payload={
                "supply_request": target_supply_instance.serialize(),
                "acquisitions": list(map(lambda x:x.serialize(), acq_instances.items)),
                **qp.get_pagination_form(acq_instances)
            }
        ).to_json()

    #acquisition_id is present in query parameters
    valid, msg = IntegerHelpers.is_valid_id(acq_id)
    if not valid:
        raise APIException.from_error(EM({"acquisition_id": msg}).bad_request)

    target_acq_instance = q.filter(Acquisition.id == acq_id).first()
    if not target_acq_instance:
        raise APIException.from_error(EM({"acquisition_id": f"ID-{acq_id} not found"}).notFound)

    return JSONResponse(
        message=f"return acquisition_id: {acq_id} from supply_request_id: {sr_id}",
        payload={"acquisition": target_acq_instance.serialize_all()}
    ).to_json()


@operations_bp.route("/supply-requests/<int:sr_id>/acquisitions", methods=["POST"])
@json_required({"item_id": int, "item_qtty": float, "item_cost": float})
@role_required(level=1)
def create_acquisition(role, body, sr_id):

    item_id = body["item_id"]
    invalids = Validations.validate_inputs({
        "item_id": IntegerHelpers.is_valid_id(item_id),
        "supply_request_id": IntegerHelpers.is_valid_id(sr_id)
    })
    newRows, invalid_body = update_row_content(Acquisition, body)
    invalids.update(invalid_body)

    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    target_sr = db.session.query(SupplyRequest.id).filter(SupplyRequest.company_id == role.company.id).\
        filter(SupplyRequest.id == sr_id).first()
    if not target_sr:
        raise APIException.from_error(EM({"supply_request_id": f"ID-{sr_id} not found"}).notFound)

    target_item = db.session.query(Item.id).filter(Item.company_id == role.company.id).\
        filter(Item.id == item_id).first()
    if not target_item:
        raise APIException.from_error(EM({"item_id": f"ID-{item_id} not found"}).notFound)

    if "provider_id" in body:
        provider_id = body["provider_id"]
        valid, msg = IntegerHelpers.is_valid_id(provider_id)
        if not valid:
            raise APIException.from_error(EM({"provider_id": msg}).bad_request)

        target_provider = db.session.query(Provider).filter(Provider.company_id == role.company.id).\
            filter(Provider.id == provider_id).first()

        if not target_provider:
            raise APIException.from_error(EM({"provider_id": f"ID-{provider_id} not found"}).notFound)

        newRows.update({"provider_id": provider_id})
    
    newRows.update({
        "item_id": item_id,
        "supply_request_id": sr_id
    })

    newAcquisition = Acquisition(**newRows)

    try:
        db.session.add(newAcquisition)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message="new Acquisition created",
        status_code=201,
        payload={
            "acquisition": newAcquisition.serialize_all()
        }
    ).to_json()


@operations_bp.route("/supply-requests/acquisitions/<int:acq_id>", methods=["PUT", "DELETE"])
@json_required()
@role_required(level=1)
def update_or_delete_acquisition(role, acq_id, body=None):

    valid, msg = IntegerHelpers.is_valid_id(acq_id)
    if not valid:
        raise APIException.from_error(EM({"acquisition_id": msg}).bad_request)

    target_acq = db.session.query(Acquisition).select_from(Company).join(Company.supply_requests).\
        join(SupplyRequest.acquisitions).filter(Company.id == role.company.id, Acquisition.id == acq_id).first()

    if not target_acq:
        raise APIException.from_error(EM({"acquisition_id": f"ID-{acq_id} not found"}).notFound)

    if request.method == "DELETE":

        try:
            db.session.delete(target_acq)
            db.session.commit()
        
        except IntegrityError as ie:
            raise APIException.from_error(EM(
                {"acquisition_id": f"can't delete acquisition_id-{acq_id} - {ie}"}
            ).bad_request)

        except SQLAlchemyError as e:
            handle_db_error(e)

        return JSONResponse(
            message=f"Acquisition-id-{acq_id} deleted"
        ).to_json()

    #if request.method == "PUT"
    newRows, invalids = update_row_content(Acquisition, body)
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    try:
        db.session.query(Acquisition).filter(Acquisition.id == acq_id).update(newRows)
        db.session.commit()

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message=f"Acquisition id-{acq_id} updated"
    ).to_json()


@operations_bp.route("/order-requests", methods=["GET"])
@json_required()
@role_required(level=1)
def get_order_requests(role):

    qp = QueryParams(request.args)
    or_id = qp.get_first_value("id", as_integer=True)

    q = db.session.query(OrderRequest).select_from(Company).join(Company.order_requests).\
        filter(Company.id == role.company.id)

    if not or_id:

        # add filters here

        page, limit = qp.get_pagination_params()
        or_instances = q.paginate(page, limit)

        return JSONResponse(
            message=qp.get_warings(),
            payload={
                "order_requests": list(map(lambda x:x.serialize(), or_instances.items)),
                **qp.get_pagination_form(or_instances)
            }
        ).to_json()

    #order_request_id in query parameters
    valid, msg = IntegerHelpers.is_valid_id(or_id)
    if not valid:
        raise APIException.from_error(EM({"order_request_id": msg}).bad_request)

    target_orq_instance = q.filter(OrderRequest.id == or_id).first()
    if not target_orq_instance:
        raise APIException.from_error(EM({"order_request_id": f"ID-{or_id} not found"}).notFound)

    return JSONResponse(
        message=f"return order-request-{or_id} data",
        payload={
            "order_request": target_orq_instance.serialize_all()
        }
    ).to_json()
    


@operations_bp.route("/order-requests/<int:orq_id>/orders")
@json_required()
@role_required(level=1)
def get_orders_in_orq(role, orq_id):

    qp = QueryParams(request.args)
    valid, msg = IntegerHelpers.is_valid_id(orq_id)
    if not valid:
        raise APIException.from_error(EM({"order_request_id": msg}).bad_request)

    target_orq_instance = db.sesison.query(OrderRequest.id).select_from(Company).\
        join(Company.order_requests).filter(Company.id == role.company.id, OrderRequest.id == orq_id).first()

    if not target_orq_instance:
        raise APIException.from_error(EM({"order_request_id": f"ID-{orq_id} not found"}).notFound)

    q = db.session.query(Order).select_from(Company).join(Company.order_requests).join(OrderRequest.orders).\
        filter(Company.id == role.company.id, OrderRequest.id == orq_id)
    
    ord_id = qp.get_first_value("id", as_integer=True)
    if not ord_id:

        # add filters here

        page, limit = qp.get_pagination_params()
        ord_instances = q.paginate(page, limit)

        return JSONResponse(
            message=qp.get_warings(),
            payload={
                "order_request": target_orq_instance.serialize(),
                "orders": list(map(lambda x:x.serialize(), ord_instances.items)),
                **qp.get_pagination_form(ord_instances)
            }
        ).to_json()

    #order_id in query parameters
    valid, msg = IntegerHelpers.is_valid_id(ord_id)
    if not valid:
        raise APIException.from_error(EM({"order_id": msg}).bad_request)

    target_order = q.filter(Order.id == ord_id).first()
    if not target_order:
        raise APIException.from_error(EM({"order_id": f"ID-{ord_id} not found"}))
    
    return JSONResponse(
        message=f"return order-{ord_id} in order_request_id-{orq_id}",
        payload={"order": target_order.serialize_all()}
    ).to_json()



# acquisitions/     [GET, POST]
# acquisitions/<int:acq_id>     [PUT, DELETE]
# order-requests/   [GET]
# order-requests/<int:orq_id>   [GET]
# order-requests/<int:orq_id>/items     [GET]
# order-requests/items/<int:item_id>    [GET, PUT, DELETE]
# order-requests/items/<int:item_id>/requisitions   [GET, POST]
# order-requests/items/requisitions/<int:req_id>    [PUT, DELETE]