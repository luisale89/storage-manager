import logging
from datetime import datetime
from app.extensions import db
from app.models.main import Company, Container, Inventory, Storage
from app.utils.helpers import StringHelpers, DateTimeHelpers
from app.utils.func_decorators import app_logger
from flask import abort
from sqlalchemy.sql.functions import ReturnTypeFromArgs
from sqlalchemy import func
ReturnTypeFromArgs.inherit_cache = True

logger = logging.getLogger(__name__)


@app_logger(logger)
def update_row_content(model, new_row_data: dict) -> tuple:
    """
    Funcion para actualizar el contenido de una fila de cualquier tabla en la bd.
    Recorre cada item del parametro <new_row_data> y determina si el nombre coincide con el nombre de una de las
     columnas.
    en caso de coincidir, se hacen validaciones sobre el contenido, si coincide con la instancia esperada en la
    columna de la bd y se devuelve un diccionario con los valores a actualizar en el modelo.

    * Parametros:

    1. model: instancia de los modelos de la bd
    2. new_row_data: diccionario con el contenido a actualizar en el modelo. Generalmente es el body del request
    recibido en el endpoint
        request.get_json()..

    *
    Respuesta:
    -> tuple con el formato: (to_update:{dict}, invalids:[list], message:str)

    Raises:
    -> APIExceptions ante cualquier error de instancias, cadena de caracteres erroneas, etc.

    """
    table_columns = model.__table__.columns
    to_update = {}
    invalids = {}

    for row, content in new_row_data.items():
        if row in table_columns:  # si coinicide el nombre del parmetro con alguna de las columnas de la db
            data = table_columns[row]
            if data.name.startswith("_") or data.primary_key or data.name.endswith("_id"):
                continue  # columnas que cumplan con los criterios anteriores no se pueden actualizar en esta funcion.

            column_type = data.type.python_type

            if not isinstance(content, column_type):
                invalids.update({row: f"invalid instance, [{column_type.__name__}] is expected"})
                continue

            if column_type == datetime:
                content = DateTimeHelpers(content).normalize_datetime()
                if not content:
                    invalids.update({row: f"invalid datetime format, {content} was received"})
                    continue  # continue with the next loop

            if isinstance(content, str):
                sh = StringHelpers(string=content)
                valid, msg = sh.is_valid_string(max_length=data.type.length)
                if not valid:
                    invalids.update({row: msg})
                    continue

                content = sh.normalize(spaces=True)

            if isinstance(content, list) or isinstance(content, dict):  # formatting json content
                content = {f"{table_columns[row].name}": content}

            to_update[row] = content

    if not to_update:
        invalids.update({"empty_params": 'no match were found between app-parameters and parameters in body'})

    return to_update, invalids


def handle_db_error(error):
    """handle SQLAlchemy Exceptions and errors"""
    db.session.rollback()
    abort(500, f"{error}")


class Unaccent(ReturnTypeFromArgs):
    pass


class ContainerValidations():
    def __init__(self, company_id:int, container_id:int):
        self.company_id = company_id
        self.container_id = container_id
        self.dbInstance = db.session.query(Container).select_from(Company).join(Company.storages).\
            join(Storage.containers).filter(Company.id == company_id, Container.id == container_id).first()

    def __repr__(self) -> str:
        return f"ContainerValidations(company_id={self.company_id}, container_id={self.container_id})"

    @property
    def is_found(self) -> bool:
        return True if self.dbInstance else False

    @property
    def not_found_message(self) -> str:
        return f"container ID-{self.container_id} not found"

    @property
    def conflict_message(self) -> str:
        return f"container-{self.container_id} holds a different item-id, find another container to save current item"

    def sameItemContained(self, newItemID:int) -> bool:
        '''Method that returns a boolean indicating if te newItemID to be included in the container
        is the same as the ones that already exists inside the container. 
        '''
        container = self.dbInstance
        if container.inventories:
            same_item = container.inventories.filter(Inventory.acquisition.item_id == newItemID).first()
            return True if same_item else False
        
        #if container is empty, returns True
        return True