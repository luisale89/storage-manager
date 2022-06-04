from flask import Blueprint
from app.models.global_models import RoleFunction

#extensions
from app.models.main import Company, UnitCatalog, User, Role, Provider, Category, Attribute
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import ErrorMessages, JSONResponse, random_password, remove_repeated
from app.utils.route_decorators import json_required, role_required
from app.utils.db_operations import handle_db_error, update_row_content
from app.utils.route_helper import get_pagination_params, pagination_form
from app.utils.validations import validate_email
from app.utils.email_service import send_user_invitation


company_bp = Blueprint('company_bp', __name__)

#*1
@company_bp.route('/', methods=['GET'])
@json_required()
@role_required()
def get_user_company(role):

    resp = JSONResponse(payload={
        "company": role.company.serialize_all()
    })
    return resp.to_json()

#*2
@company_bp.route('/', methods=['PUT'])
@json_required()
@role_required(level=0) #owner only
def update_company(role, body):

    to_update, invalids, msg = update_row_content(Company, body)
    if invalids != []:
        raise APIException.from_error(ErrorMessages(parameters=invalids, custom_msg=msg).bad_request)

    try:
        Company.query.filter(Company.id == role.company.id).update(to_update)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f'Company updated').to_json()

#*3
@company_bp.route('/users', methods=['GET'])
@json_required()
@role_required(level=1)#andmin user
def get_company_users(role):

    roles = db.session.query(Role).join(Role.user).filter(Role._company_id == role.company.id).order_by(func.lower(User.fname).asc()).all()
    return JSONResponse(payload={
        "users": list(map(lambda x: {**x.user.serialize(), "role": x.serialize_all()}, roles))
    }).to_json()

#*4
@company_bp.route('/users', methods=['POST'])
@json_required({"email": str, "role_id": int})
@role_required(level=1)
def invite_user(role, body):

    email = body['email'].lower()
    
    valid, msg = validate_email(email)
    if not valid:
        raise APIException.from_error(ErrorMessages('email', custom_msg=msg).bad_request)

    new_role_function = RoleFunction.get_rolefunc_by_id(body['role_id'])
    if new_role_function is None:
        raise APIException.from_error(ErrorMessages("role_id").notFound)

    if role.role_function.level > new_role_function.level:
        raise APIException.from_error(ErrorMessages("role_level").unauthorized)

    user = User.get_user_by_email(email)
    #nuevo usuario...
    if user is None:

        success, message = send_user_invitation(user_email=email, company_name=role.company.name)
        if not success:
            raise APIException.from_error(ErrorMessages(parameters='email-service', custom_msg=message).service_unavailable)

        try:
            new_user = User(
                email=email,
                password = random_password(),
                _email_confirmed=False,
                _signup_completed=False,
            )
            new_role = Role(
                user = new_user,
                _company_id = role._company_id,
                role_function = new_role_function
            )
            db.session.add_all([new_user, new_role])
            db.session.commit()
        except SQLAlchemyError as e:
            handle_db_error(e)

        return JSONResponse("new user invited", status_code=201).to_json()

    #ususario existente...
    rel = db.session.query(User).join(User.roles).join(Role.company).\
        filter(User.id == user.id, Company.id == role._company_id).first()
    
    if rel is not None:
        raise APIException.from_error(
            ErrorMessages('email', custom_msg=f'User <{email}> is already listed in current company').conflict
        )
    
    sended, error = send_user_invitation(user_email=email, user_name=user.fname, company_name=role.company.name)
    if not sended:
        raise APIException.from_error(ErrorMessages(parameters='email-service', custom_msg=error).service_unavailable)
        
    try:
        new_role = Role(
            _company_id = role._company_id,
            user = user,
            role_function = new_role_function
        )
        db.session.add(new_role)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse('existing user invited').to_json()

#*5
@company_bp.route('/users/<int:user_id>', methods=['PUT'])
@json_required({'role_id':int, 'is_active':bool})
@role_required(level=1)
def update_user_company_relation(role, body, user_id=None):

    role_id = body['role_id']
    new_status = body['is_active']
    error = ErrorMessages()

    target_role = Role.get_relation_user_company(user_id, role.company.id)
    if target_role is None:
        error.parameters.append('user_id')
    
    new_rolefunction = RoleFunction.get_rolefunc_by_id(role_id)
    if new_rolefunction is None:
        error.parameters.append('role_id')

    if error.parameters != []:
        raise APIException.from_error(error.notFound)

    if role.role_function.level > new_rolefunction.level:
        raise APIException.from_error(ErrorMessages("role_level").unauthorized)
        
    try:
        target_role.role_function = new_rolefunction
        target_role._isActive = new_status
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse("user role updated").to_json()

#*6
@company_bp.route('/users/<int:user_id>', methods=['DELETE'])
@json_required()
@role_required(level=1)
def delete_user_company_relation(role, user_id=None):

    target_role = Role.get_relation_user_company(user_id, role.company.id)
    if target_role is None:
        raise APIException.from_error(ErrorMessages('user_id').notFound)
    try:
        db.session.delete(target_role)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse("user was deleted of current company").to_json()

#*7
@company_bp.route('/roles', methods=['GET'])
@json_required()
@role_required()#any user
def get_company_roles(role):

    return JSONResponse(payload={
        "roles": list(map(lambda x: x.serialize(), db.session.query(RoleFunction).all()))
    }).to_json()


#8
@company_bp.route('/providers', methods=['GET'])
@company_bp.route('providers/<int:provider_id>', methods=['GET'])
@json_required()
@role_required(level=1)
def get_company_providers(role, provider_id=None):
    
    if provider_id is None:
        page, limit = get_pagination_params()
        providers = role.company.providers.paginate(page, limit)

        return JSONResponse(payload={
            'providers': list(map(lambda x: x.serialize(), providers.items)),
            **pagination_form(providers)
        }).to_json()
    
    #provider_id in url
    provider = role.company.get_provider(provider_id)
    if provider is None:
        raise APIException.from_error(ErrorMessages(parameters='provider_id').notFound)

    return JSONResponse(
        payload={'provider': provider.serialize_all()}
    ).to_json()


#9
@company_bp.route('/providers', methods=['POST'])
@json_required({'name': str})
@role_required(level=1)
def create_provider(role, body):

    error = ErrorMessages()

    to_add, invalids, msg = update_row_content(Provider, body)

    if invalids != []:
        error.parameters.append(invalids)
        error.custom_msg = msg
        raise APIException.from_error(error.bad_request)

    to_add.update({'_company_id': role.company.id}) #se agrega company

    new_provider = Provider(**to_add)

    try:
        db.session.add(new_provider)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message='new provider was created', 
        payload={
        'provider': new_provider.serialize_all()
        },
        status_code=201
    ).to_json()


#10
@company_bp.route('/providers/<int:provider_id>', methods=['PUT'])
@json_required()
@role_required(level=1)
def update_provider(role, body, provider_id):

    error = ErrorMessages()
    provider = role.company.get_provider(provider_id)
    if provider is None:
        error.parameters.append('provider_id')
        raise APIException.from_error(error.notFound)

    to_update, invalids, msg = update_row_content(Provider, body)
    if invalids != []:
        error.parameters.append(invalids)
        error.custom_msg = msg
        raise APIException.from_error(error.bad_request)

    try:
        db.session.query(Provider).filter(Provider.id == provider.id).update(to_update)
        db.session.commit()

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(message=f'provider-id: {provider_id} was updated').to_json()


#11
@company_bp.route('/providers/<int:provider_id>', methods=['DELETE'])
@json_required()
@role_required(level=1)
def delete_provider(role, provider_id):

    error = ErrorMessages()
    provider = role.company.get_provider(provider_id)
    if provider is None:
        error.parameters.append('provider_id')
        raise APIException.from_error(error.notFound)

    try:
        db.session.delete(provider)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(message=f'provider-id: {provider_id} was deleted').to_json()


#12
@company_bp.route('/units', methods=['GET'])
@company_bp.route('/units/<int:unit_id>', methods=['GET'])
@json_required()
@role_required()
def get_units(role, unit_id=None):

    if unit_id is None:
        page, limit = get_pagination_params()
        units = role.company.units_catalog.paginate(page, limit)

        return JSONResponse(
            payload={
                'units': list(map(lambda x:x.serialize(), units.items)),
                **pagination_form(units)
            }
        ).to_json()

    unit = role.company.get_unit(unit_id)
    if unit is None:
        raise APIException.from_error(ErrorMessages(parameters='unit_id').notFound)

    return JSONResponse(
        payload={
            'unit': unit.serialize_all()
        }
    ).to_json()


#13
@company_bp.route('/units', methods=['POST'])
@json_required({'name': str})
@role_required(level=1)
def create_unit(role, body):
    
    error = ErrorMessages()

    to_add, invalids, msg = update_row_content(UnitCatalog, body)
    if invalids != []:
        error.parameters.append(invalids)
        error.custom_msg = msg
        raise APIException.from_error(error.bad_request)

    to_add.update({'_company_id': role.company.id})
    new_unit = UnitCatalog(**to_add)
    try:
        db.session.add(new_unit)
        db.session.commit()

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message='new unit created',
        status_code=201,
        payload=new_unit.serialize()
    ).to_json()


#14
@company_bp.route('/units/<int:unit_id>', methods=['PUT'])
@json_required()
@role_required(level=1)
def update_unit(role, body, unit_id):

    error = ErrorMessages()
    unit =  role.company.get_unit(unit_id)
    if unit is None:
        error.parameters.append('unit_id')
        raise APIException.from_error(error.notFound)

    to_update, invalids, msg = update_row_content(UnitCatalog, body)
    if invalids != []:
        error.parameters.append(invalids)
        error.custom_msg = msg
        raise APIException.from_error(error.bad_request)

    try:
        db.session.query(UnitCatalog).filter(UnitCatalog.id == unit.id).update(to_update)
        db.session.commit()

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message=f'unit-id: {unit_id} updated'
    ).to_json()


#15
@company_bp.route('/units/<int:unit_id>', methods=['DELETE'])
@json_required()
@role_required(level=1)
def delete_unit(role, unit_id):

    error = ErrorMessages()
    target_unit = role.company.get_unit(unit_id)
    if target_unit is None:
        error.parameters.append('unit_id')
        raise APIException.from_error(error.notFound)

    if target_unit.attribute_values.all() != []:
        error.custom_msg = f"can't delete unit_id: {unit_id}, some attributes has been assigned to it"
        raise APIException.from_error(error.conflict)

    try:
        db.session.delete(target_unit)
        db.session.commit()
    
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message='unit has been deleted'
    ).to_json()

#16
@company_bp.route('/categories', methods=['GET'])
@company_bp.route('/categories/<int:category_id>', methods=['GET'])
@json_required()
@role_required()
def get_company_categories(role, category_id=None):

    if category_id == None:
        cat = role.company.categories.filter(Category.parent_id == None).order_by(Category.name.asc()).all() #root categories only
        
        return JSONResponse(
            message="ok",
            payload={
                "categories": list(map(lambda x: x.serialize_children(), cat))
            }
        ).to_json()

    #category-id is present in the route
    cat = role.company.get_category_by_id(category_id)
    if cat is None:
        raise APIException.from_error(ErrorMessages("category_id").notFound)

    #return item
    return JSONResponse(
        message="ok",
        payload={
            'category': cat.serialize_all()
        }
    ).to_json()


#17
@company_bp.route('/categories', methods=['POST'])
@company_bp.route('/categories/<int:category_id>', methods=['PUT'])
@json_required({'name': str})
@role_required()
def create_or_update_category(role, body, category_id=None):

    parent_id = body.get('parent_id', None)
    error = ErrorMessages()

    if parent_id is not None:
        parent = role.company.get_category_by_id(parent_id)
        if parent is None:
            error.parameters.append('parent_id')
            raise APIException.from_error(error.notFound)

    to_add, invalids, msg = update_row_content(Category, body)
    if invalids != []:
        error.parameters.append(invalids)
        error.custom_msg = msg
        raise APIException.from_error(error.bad_request)

    if category_id is None:
        to_add.update({'_company_id': role.company.id})
        new_category = Category(**to_add)

        try:
            db.session.add(new_category)
            db.session.commit()
        except SQLAlchemyError as e:
            handle_db_error(e)

        return JSONResponse(
            payload={"category": new_category.serialize()},
            status_code=201
        ).to_json()

    target_cat = role.company.get_category_by_id(category_id)
    if target_cat is None:
        error.parameters.append('category_id')
        raise APIException.from_error(error.notFound)

    try:
        db.session.query(Category).filter(Category.id == target_cat.id).update(to_add)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f'category-id: {category_id} updated').to_json()


#18
@company_bp.route('/categories/<int:category_id>/attributes', methods=['PUT'])
@json_required({'attributes': list})
@role_required(level=1)
def update_category_attributes(role, body, category_id):

    error = ErrorMessages()
    attributes = body.get('attributes')
    target_cat = role.company.get_category_by_id(category_id)

    if target_cat is None:
        error.parameters.append('category_id')
        raise APIException.from_error(error.notFound)

    if attributes == []:
        #empty list clear all attibutes
        try:
            target_cat.attributes = []
            db.session.commit()
        except SQLAlchemyError as e:
            handle_db_error(e)

        return JSONResponse(
            message=f'all attributes of category-id: {category_id} were deleted',
        ).to_json()

    not_integer = [r for r in attributes if not isinstance(r, int)]
    if not_integer != []:
        error.parameters.append('attributes')
        error.custom_msg = f'list of attributes must include integers values only.. <{not_integer}> were detected'
        raise APIException.from_error(error.bad_request)

    new_attributes = role.company.attributes.filter(Attribute.id.in_(attributes)).all()
    if new_attributes is None:
        error.parameters.append('attributes')
        error.custom_msg = f'no attributes were found in the database'
        raise APIException.from_error(error.notFound)

    #remove_attributes that exists in parent categories
    p_attributes = target_cat.get_attributes()
    new_attributes = remove_repeated(new_attributes, p_attributes)
    if new_attributes == []:
        return JSONResponse(
            message=f'no changes in category-id:{category_id}',
            payload={
                'category': target_cat.serialize()
            }
        ).to_json()

    try:
        target_cat.attributes.extend(new_attributes)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message=f'category-id: {category_id} updated',
        payload={
            'category': target_cat.serialize()
        }
    ).to_json()


#19
@company_bp.route('/categories/<int:category_id>', methods=['DELETE'])
@json_required()
@role_required()
def delete_category(role, category_id=None):

    cat = role.company.get_category_by_id(category_id)
    if cat is None:
        raise APIException.from_error(ErrorMessages("category_id").notFound)

    try:
        db.session.delete(cat)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f"Category id: <{category_id}> has been deleted").to_json()


@company_bp.get('/categories/attributes')
@company_bp.get('/categories/attributes/<int:attribute_id>')
@json_required()
@role_required()
def get_company_attributes(role, attribute_id=None):

    if attribute_id == None:

        page, limit = get_pagination_params()
        attributes = role.company.attributes.order_by(Attribute.name.asc()).paginate(page, limit)

        return JSONResponse(
            payload={
                'attributes': list(map(lambda x:x.serialize(), attributes.items)),
                **pagination_form(attributes)
            }
        ).to_json()

    error = ErrorMessages()
    target_attr = role.company.get_attribute(attribute_id)
    if target_attr is None:
        error.parameters.append('attribute_id')
        raise APIException.from_error(error.notFound)

    return JSONResponse(
        payload={
            'attribute': target_attr.serialize()
        }
    ).to_json()


#20
@company_bp.post('/categories/attributes')
@json_required({'name': str})
@role_required(level=1)    
def create_attribute(role, body):

    error = ErrorMessages()
    to_add, invalids, msg = update_row_content(Attribute, body)

    if invalids != []:
        error.parameters.append(invalids)
        error.custom_msg = msg
        raise APIException.from_error(error.bad_request)
    
    to_add.update({'_company_id': role.company.id})
    new_attribute = Attribute(**to_add)

    try:
        db.session.add(new_attribute)
        db.session.commit()

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        payload={
            'attribute': new_attribute.serialize()
        },
        message='new attribute created',
        status_code=201
    ).to_json()


#21
@company_bp.put('/categories/attributes/<int:attribute_id>')
@json_required()
@role_required(level=1)
def update_attribute(role, body, attribute_id):

    error = ErrorMessages()
    target_attr = role.company.get_attribute(attribute_id)
    if target_attr is None:
        error.parameters.append('attribute_id')
        raise APIException.from_error(error.notFound)

    to_update, invalids, msg = update_row_content(Attribute, body)
    if invalids != []:
        error.parameters.append(invalids)
        error.custom_msg = msg
        raise APIException.from_error(error.bad_request)
    
    try:
        db.session.query(Attribute).filter(Attribute.id == target_attr.id).update(to_update)
        db.session.commit()

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message=f'attribute-id: {attribute_id} updated'
    ).to_json()


#22
@company_bp.delete('/categories/attributes/<int:attribute_id>')
@json_required()
@role_required(level=1)
def delete_attribute(role, attribute_id):

    error = ErrorMessages()
    target_attr = role.company.get_attribute(attribute_id)
    if target_attr is None:
        error.parameters.append('attribute_id')
        raise APIException.from_error(error.notFound)

    values = target_attr.attribute_values.all()

    if values != []:
        error.custom_msg = 'can not delete current attribute, some values depend on it'
        raise APIException.from_error(error.notAcceptable)

    try:
        db.session.delete(target_attr)
        db.session.commit()

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f'attribute_id: {attribute_id} deleted').to_json()