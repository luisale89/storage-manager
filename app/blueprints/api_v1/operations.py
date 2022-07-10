from crypt import methods
from flask import Blueprint

#models
from app.models.main import Acquisition
from app.extensions import db
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import ErrorMessages, JSONResponse, QueryParams
from app.utils.route_helper import get_pagination_params, pagination_form
from app.utils.route_decorators import json_required, role_required
from app.utils.db_operations import handle_db_error, update_row_content

operations_bp = Blueprint("operations_bp", __name__)

# prefix: operations/

# endpoints:

# acquisitions/     [GET, POST]
# acquisitions/<int:acq_id>     [PUT, DELETE]
# inventory/    [GET, POST]
# inventory/<int:inv_id>    [PUT, DELETE]
# inventory/<int:inv_id>/review     [GET, POST]
# order-requests/   [GET]
# order-requests/<int:orq_id>   [GET]
# order-requests/<int:orq_id>/items     [GET]
# order-requests/items/<int:item_id>    [GET, PUT, DELETE]
# order-requests/items/<int:item_id>/requisitions   [GET, POST]
# order-requests/items/requisitions/<int:req_id>    [PUT, DELETE]