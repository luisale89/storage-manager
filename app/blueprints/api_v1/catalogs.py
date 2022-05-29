from flask import Blueprint, request

#extensions
from app.models.main import Attribute, UnitCatalog
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError

#utils
from app.utils.helpers import JSONResponse
from app.utils.route_decorators import json_required, role_required
from app.utils.db_operations import handle_db_error, update_row_content
from app.utils.route_helper import get_pagination_params, pagination_form

catalogs_bp = Blueprint('catalogs_bp', __name__)