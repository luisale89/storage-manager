from sqlalchemy import table
from app.models.main import (
    User
)
from app.utils.exceptions import APIException
from app.extensions import db
from app.utils.helpers import ErrorMessages, normalize_names
from app.utils.validations import validate_string

def get_user_by_email(email):
    '''
    Helper function to get user from db, email parameter is required
    '''
    # user = User.query.filter_by(email=email).first()
    user = db.session.query(User).filter(User._email == email).first()

    if user is None:
        raise APIException(f"email: {email} not found in database", status_code=404, app_result="not found")

    return user

def get_user_by_id(user_id, company_required=False):
    '''
    Helper function to get user from db, using identifier
    '''
    if user_id is None:
        raise APIException("user_id not found in jwt")

    user = db.session.query(User).get(user_id)

    if company_required and user.company is None:
        raise APIException("user has no company", app_result="no_content")

    if user is None:
        raise APIException(f"user_id: {user_id} does not exists in database", status_code=404, app_result='not found')

    return user


def update_row_content(model, new_row_data:dict) -> dict:
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

    for key in new_row_data:
        if key in table_columns:
            if table_columns[key].name[0] == '_' or table_columns[key].foreign_keys or table_columns[key].primary_key:
                continue #columnas que cumplan con los criterios anteriores no se pueden actualizar en esta funcion.

            column_type = table_columns[key].type.python_type
            content = new_row_data[key]

            if not isinstance(content, column_type):
                raise APIException(f"{ErrorMessages().invalidInput} - Expected: {column_type}, received {type(content)} in <'{key}'> parameter")
            if isinstance(content, str):
                check = validate_string(content, max_length=table_columns[key].type.length)
                if check['error']:
                    raise APIException(message=f"{check['msg']} - parameter received: <{key}:{content}>")

                content = normalize_names(content, spaces=True)

            to_update[key] = content
    
    if to_update == {}:
        raise APIException(f"{ErrorMessages().invalidInput}")

    return to_update