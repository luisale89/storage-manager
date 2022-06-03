import logging
from datetime import datetime
from app.extensions import db
from app.utils.helpers import normalize_string, normalize_datetime
from app.utils.validations import validate_string
from app.utils.func_decorators import app_logger
from flask import abort

logger = logging.getLogger(__name__)

@app_logger(logger)
def update_row_content(model, new_row_data:dict) -> tuple:
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
    -> tuple con el formato: (to_update:{dict}, invalids:[list], message:str)

    Raises:
    -> APIExceptions ante cualquier error de instancias, cadena de caracteres erroneas, etc.

    '''
    table_columns = model.__table__.columns
    to_update = {}
    invalids = []
    messages = []

    for row in new_row_data:
        if row in table_columns: #si coinicide el nombre del parmetro con alguna de las columnas de la db
            if table_columns[row].name[0] == '_' or table_columns[row].primary_key:
                continue #columnas que cumplan con los criterios anteriores no se pueden actualizar en esta funcion.

            column_type = table_columns[row].type.python_type
            content = new_row_data[row]
            if isinstance(content, list) or isinstance(content, dict): #formatting json content
                content = {table_columns[row].name: content}

            if not isinstance(content, column_type):
                invalids.append(row)
                messages.append(f"[{row}]: invalid instance, '{column_type.__name__}' is expected")
                continue

            if column_type == datetime:
                content = normalize_datetime(content)
                if content is None:
                    invalids.append(row)
                    messages.append(f'[{row}]: invalid datetime format')
                    continue #continue with the next loop

            if isinstance(content, str):
                valid, msg = validate_string(content, max_length=table_columns[row].type.length)
                if not valid:
                    invalids.append(row)
                    messages.append(f'[{row}]: {msg}')
                    continue

                content = normalize_string(content, spaces=True)

            to_update[row] = content

    return (to_update, invalids, ' | '.join(messages))


def handle_db_error(error):
    '''handle SQLAlchemy Exceptions and errors'''
    db.session.rollback()
    abort(500, error)