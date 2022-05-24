from app.models.main import (
    Attribute, Category, Shelf, UnitCatalog, Item, Storage, Company, Stock
)
from sqlalchemy import func
from datetime import datetime
from app.utils.exceptions import APIException
from app.extensions import db
from app.utils.helpers import ErrorMessages, normalize_string, normalize_datetime
from app.utils.validations import validate_string
from flask import abort

class ValidRelations():

    def __init__(self, silent=False):
        self.silent = silent

    def company_storage(self, company_id:int, storage_id:int):
        strg = db.session.query(Storage).join(Storage.company).\
            filter(Company.id == company_id, Storage.id == storage_id).first()
        if strg is None and not self.silent:
            raise APIException(f"{ErrorMessages('storage_id').notFound}", status_code=404)

        return strg
        
    def company_stock(self, company_id:int, item_id:int, storage_id:int):
        stock = db.session.query(Stock).select_from(Company).join(Company.items).join(Item.stock).join(Stock.storage).\
            filter(Company.id == company_id, Item.id == item_id, Storage.id == storage_id).first()
        if stock is None and not self.silent:
            raise APIException(f"{ErrorMessages('item_id').notFound} isn't related with storage-id:<{storage_id}>", status_code=404)

        return stock

    def company_attributes(self, company_id:int, attribute_id:int):
        attr = db.session.query(Attribute).join(Attribute.company).\
            filter(Company.id == company_id, Attribute.id == attribute_id).first()

        if attr is None and not self.silent:
            raise APIException(f"{ErrorMessages('attribute_id').notFound}", status_code=404)

        return attr

    def company_units(self, company_id:int, unit_id:int):
        unit = db.session.query(UnitCatalog).join(UnitCatalog.company).\
            filter(Company.id == company_id, UnitCatalog.id == unit_id).first()

        if unit is None and not self.silent:
            raise APIException(f"{ErrorMessages('unit_id').notFound}", status_code=404)

        return unit

    def storage_shelf(self, company_id:int, storage_id:int, shelf_id:int):
        storage = self.company_storage(company_id, storage_id)
        shelf = storage.shelves.filter(Shelf.id == shelf_id).first()
        if shelf is None and not self.silent:
            raise APIException(f"{ErrorMessages('shelf_id').notFound}", status_code=404)

        return shelf


def update_row_content(model, new_row_data:dict, silent:bool=False) -> dict:
    '''
    Funcion para actualizar el contenido de una fila de cualquier tabla en la bd.
    Recorre cada item del parametro <new_row_data> y determina si el nombre coincide con el nombre de una de las columnas.
    en caso de coincidir, se hacen validaciones sobre el contenido, si coincide con la instancia esperada en la columna de la bd
    y se devuelve un diccionario con los valores a actualizar en el modelo.

    * Parametros:

    1. model: instancia de los modelos de la bd
    2. new_row_data: diccionario con el contenido a actualizar en el modelo. Generalmente es el body del request recibido en el endpoint
        request.get_json()..

    *
    Respuesta:
    -> dict con los pares <key>:<value> a actualizar en la tabla.

    Raises:
    -> APIExceptions ante cualquier error de instancias, cadena de caracteres erroneas, etc.

    '''
    table_columns = model.__table__.columns
    to_update = {}
    for row in new_row_data:
        if row in table_columns:
            if table_columns[row].name[0] == '_' or table_columns[row].primary_key:
                continue #columnas que cumplan con los criterios anteriores no se pueden actualizar en esta funcion.

            column_type = table_columns[row].type.python_type
            content = new_row_data[row]

            if column_type == datetime:
                content = normalize_datetime(content)
                if content is None:
                    raise APIException.from_error(ErrorMessages(parameters=[row], custom_msg='invalid datetime format').bad_request)

            if not isinstance(content, column_type):
                raise APIException.from_error(ErrorMessages(parameters=[row], custom_msg='Invalid format in request').bad_request)
            
            if isinstance(content, str):
                check = validate_string(content, max_length=table_columns[row].type.length)
                if check['error']:
                    raise APIException.from_error(ErrorMessages(parameters=[row], custom_msg='Invalid format in request').bad_request)
                
                content = normalize_string(content, spaces=True)

            to_update[row] = content

    if to_update == {} and not silent:
        raise APIException.from_error(f"{ErrorMessages(custom_msg='Invalid parameters in request body - no match with posible inputs').bad_request}")

    return to_update


def handle_db_error(error):
    '''handle SQLAlchemy Exceptions and errors'''
    db.session.rollback()
    abort(500, error)