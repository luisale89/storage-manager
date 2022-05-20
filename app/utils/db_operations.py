import logging
from app.models.global_models import RoleFunction
from app.models.main import (
    Attribute, Category, Role, Shelf, UnitCatalog, User, Item, Storage, Company, Stock
)
from sqlalchemy import func
from datetime import datetime
from app.utils.exceptions import APIException
from app.extensions import db
from app.utils.helpers import ErrorMessages, normalize_string, normalize_datetime
from app.utils.validations import validate_string
from flask import abort

logger = logging.getLogger(__name__)
class ValidRelations():

    def __init__(self, silent=False):
        self.silent = silent

    def user_company(self, user_id:int, company_id:int):
        role = db.session.query(Role).join(Role.user).join(Role.company).\
            filter(User.id == user_id, Company.id == company_id).first()
        if role is None and not self.silent:
            raise APIException(f'{ErrorMessages("company_id").notFound()}', status_code=404)

        return role

    def company_category(self, company_id:int, category_id:int):
        cat = db.session.query(Category).join(Category.company).\
            filter(Company.id == company_id, Category.id == category_id).first()
        if cat is None and not self.silent:
            raise APIException(f"{ErrorMessages('category_id').notFound()}", status_code=404)

        return cat

    def company_item(self, company_id:int, item_id:int):
        itm = db.session.query(Item).join(Item.company).\
            filter(Company.id == company_id, Item.id == item_id).first()
        if itm is None and not self.silent:
            raise APIException(f"{ErrorMessages('item_id').notFound()}", status_code=404)

        return itm

    def company_storage(self, company_id:int, storage_id:int):
        strg = db.session.query(Storage).join(Storage.company).\
            filter(Company.id == company_id, Storage.id == storage_id).first()
        if strg is None and not self.silent:
            raise APIException(f"{ErrorMessages('storage_id').notFound()}", status_code=404)

        return strg
        
    def company_stock(self, company_id:int, item_id:int, storage_id:int):
        stock = db.session.query(Stock).select_from(Company).join(Company.items).join(Item.stock).join(Stock.storage).\
            filter(Company.id == company_id, Item.id == item_id, Storage.id == storage_id).first()
        if stock is None and not self.silent:
            self.company_item(company_id, item_id)
            self.company_storage(company_id, storage_id)
            raise APIException(f"{ErrorMessages('item_id').notFound()} isn't related with storage-id:<{storage_id}>", status_code=404)

        return stock

    def company_attributes(self, company_id:int, attribute_id:int):
        attr = db.session.query(Attribute).join(Attribute.company).\
            filter(Company.id == company_id, Attribute.id == attribute_id).first()

        if attr is None and not self.silent:
            raise APIException(f"{ErrorMessages('attribute_id').notFound()}", status_code=404)

        return attr

    def company_units(self, company_id:int, unit_id:int):
        unit = db.session.query(UnitCatalog).join(UnitCatalog.company).\
            filter(Company.id == company_id, UnitCatalog.id == unit_id).first()

        if unit is None and not self.silent:
            raise APIException(f"{ErrorMessages('unit_id').notFound()}", status_code=404)

        return unit

    def storage_shelf(self, company_id:int, storage_id:int, shelf_id:int):
        storage = self.company_storage(company_id, storage_id)
        shelf = storage.shelves.filter(Shelf.id == shelf_id).first()
        if shelf is None and not self.silent:
            raise APIException(f"{ErrorMessages('shelf_id').notFound()}", status_code=404)

        return shelf


def get_role_function(_id:int, silent=False):
    '''
    helper function to get te role's functions with an id.. 
    the roles-fuction are by default
    '''
    logger.info(f'get_role_function({_id}, {silent})')
    role_function = db.session.query(RoleFunction).get(_id)
    if role_function is None:
        logger.debug('role-function not found')
        if not silent:
            raise APIException(f'{ErrorMessages("role_id").notFound()}', status_code=404)

    logger.info('return role-function')
    return role_function


def get_user_by_email(email, silent=False):
    '''
    Helper function to get user from db, email parameter is required
    '''
    # user = User.query.filter_by(email=email).first()
    logger.info(f'get_user_by_email({email}, {silent})')
    user = db.session.query(User).filter(User._email == email).first()

    if user is None and not silent:
        raise APIException(f"{ErrorMessages('email').notFound()}", status_code=404)

    logger.info('return user')
    return user


def get_role_by_id(role_id=None, silent=False):
    '''
    Helper function to get the user's role
    '''
    logger.info(f'get_role_by_id({role_id}, {silent})')
    if role_id is None:
        abort(500, "role_id not present in function caller")

    role = db.session.query(Role).get(role_id)
    if role is None and not silent:
        raise APIException(f"role_id {role_id} not found in database", 404)

    logger.info("return role")
    return role


def get_user_by_id(user_id=None, silent=False):
    '''
    Helper function to get user from db, using identifier
    '''
    logger.info(f'get_user_by_id({user_id})')
    if user_id is None:
        abort(500, "user_id not present in function caller")

    user = db.session.query(User).get(user_id)
    
    if user is None and not silent:
        raise APIException(f"user_id: {user_id} does not exists in database", status_code=404)

    logger.info("return user")
    return user


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
    logger.info('update_row_content()')
    for key in new_row_data:
        if key in table_columns:
            logger.debug(f'<{key}> in <{model.__tablename__}> table')
            if table_columns[key].name[0] == '_' or table_columns[key].primary_key:
                logger.debug("can't update field in this function")
                continue #columnas que cumplan con los criterios anteriores no se pueden actualizar en esta funcion.

            column_type = table_columns[key].type.python_type
            content = new_row_data[key]

            if column_type == datetime:
                content = normalize_datetime(content)
                if content is None:
                    raise APIException(f"{ErrorMessages().dateFormat} <{key}:{new_row_data[key]}>")

            if not isinstance(content, column_type):
                raise APIException(f"{ErrorMessages().invalidInput} - Expected: {column_type}, received: {type(content)} in: <'{key}'> parameter")
            
            if isinstance(content, str):
                check = validate_string(content, max_length=table_columns[key].type.length)
                if check['error']:
                    raise APIException(message=f"{check['msg']} - parameter received: <{key}:{content}>")
                content = normalize_string(content, spaces=True)

            to_update[key] = content
        else:
            logger.debug(f'<{key}> not in <{model.__tablename__}> table')

    if to_update == {} and not silent:
        raise APIException(f"{ErrorMessages().invalidInput}")

    logger.info("return to_update dict")
    return to_update


def handle_db_error(error):
    db.session.rollback()
    abort(500, error)