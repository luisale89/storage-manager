from flask import (
    Blueprint
)

from app.models.main import RoleFunction, Plan
from app.utils.exceptions import APIException
from app.utils.helpers import JSONResponse
from app.utils.decorators import (json_required, super_user_required)

manage_bp = Blueprint('manage_bp', __name__)


@manage_bp.route('/set-globals', methods=['GET']) #!debug
@json_required()
# @super_user_required()
def set_app_globals():

    RoleFunction.add_default_functions()
    Plan.add_default_plans()

    resp = JSONResponse("defaults added")
    return resp.to_json()

# @manage_bp.route('/get-asset-path/<int:asset_id>', methods=['GET'])
# @json_required()
# def get_asset_path(asset_id):

#     asset = Asset.query.get(asset_id)
#     if not asset:
#         raise APIException(f"asset {asset_id} not found")
        
#     path = asset.serialize_path()
    
#     resp = JSONResponse("path to root",payload=path)

#     return resp.to_json()