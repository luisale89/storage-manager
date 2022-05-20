from flask import Blueprint, request

#extensions
from app.models.main import Attribute, UnitCatalog
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError

#utils
from app.utils.helpers import JSONResponse
from app.utils.decorators import json_required, role_required
from app.utils.db_operations import handle_db_error, update_row_content, ValidRelations
from app.utils.route_helper import get_pagination_params, pagination_form

catalogs_bp = Blueprint('catalogs_bp', __name__)

#*1
@catalogs_bp.route('/attributes', methods=['GET'])
@catalogs_bp.route('/attributes/<int:attribute_id>', methods=['GET'])
@json_required()
@role_required()
def get_all_attributes(role, attribute_id=None):

    if attribute_id == None:
        page, limit = get_pagination_params()
        attr = role.company.attributes_catalog.order_by(Attribute.name.asc()).paginate(page, limit)
        return JSONResponse(
            payload={
                "attributes": list(map(lambda x: x.serialize(), attr.items)),
                **pagination_form(attr)
            }
        ).to_json()

    attr = ValidRelations().company_attributes(role.company.id, attribute_id)
    
    return JSONResponse(payload={
        "attribute": attr.serialize()
    }).to_json()

#*2
@catalogs_bp.route('/units', methods=['GET'])
@catalogs_bp.route('/units/<int:unit_id>', methods=['GET'])
@json_required()
@role_required()
def get_all_units(role, unit_id=None):

    if unit_id == None:
        page, limit = get_pagination_params()
        units = role.company.units_catalog.order_by(UnitCatalog.name.asc()).paginate(page, limit)
        return JSONResponse(
            payload={
                "units": list(map(lambda x:x.serialize(), units.items)),
                **pagination_form(units)
            }
        ).to_json()

    unit = ValidRelations().company_units(role.company.id, unit_id)

    return JSONResponse(payload={
        "unit": unit.serialize()
    }).to_json()