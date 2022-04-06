from flask import Blueprint, request
from flask_jwt_extended import get_jwt

#extensions
from app.models.main import Storage

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import JSONResponse, pagination_form
from app.utils.decorators import json_required, user_required
from app.utils.db_operations import get_user_by_id


storages_bp = Blueprint('storages_bp', __name__)

@storages_bp.route('/', methods=['GET'])
@json_required()
@user_required()
def get_storages():

    claims = get_jwt()
    user = get_user_by_id(claims.get('user_id', None), company_required=True)

    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('limit', 20))

    s = user.company.storages.order_by(Storage.name.asc()).paginate(page, per_page)

    resp = JSONResponse(
        message='ok',
        payload={
            "storages": list(map(lambda x: x.serialize(), s.items)),
            **pagination_form(s)
        }
    )

    return resp.to_json()


@storages_bp.route('/storage-id-<storage_id>', methods=['GET'])
@json_required()
@user_required()
def get_storage_by_id(storage_id):

    claims = get_jwt()
    user = get_user_by_id(claims.get('user_id', None), company_required=True)

    s = user.company.storages.filter(Storage.id == storage_id).first()

    if s is None:
        raise APIException(f"storage-id-{storage_id} not found", status_code=404, app_result="not_found")

    resp = JSONResponse(
        message="ok",
        payload={
            "storage": s.serialize()
        }
    )

    return resp.to_json()