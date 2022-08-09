from flask import Blueprint, request

#models
from app.models.main import Company, Item, Order, OrderRequest, Storage
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
    

@operations_bp.route("/order-requests", methods=["POST"])
@json_required()
@role_required(level=1)
def create_order_request(role, body=None):

    return JSONResponse(message="in development...").to_json()


@operations_bp.route("/order-requests/<int:orq_id>/orders", methods=["GET"])
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


# order-requests/   [GET]
# order-requests/<int:orq_id>   [GET]
# order-requests/<int:orq_id>/items     [GET]
# order-requests/items/<int:item_id>    [GET, PUT, DELETE]
# order-requests/items/requisitions/<int:req_id>    [PUT, DELETE]