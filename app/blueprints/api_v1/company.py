from flask import Blueprint, request
from app.models.global_models import RoleFunction

#extensions
from app.models.main import AttributeValue, Company, User, Role, Provider, Category, Attribute
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import func

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import ErrorMessages, JSONResponse, normalize_string, random_password
from app.utils.route_decorators import json_required, role_required
from app.utils.db_operations import handle_db_error, update_row_content
from app.utils.route_helper import get_pagination_params, pagination_form
from app.utils.validations import validate_email, validate_id
from app.utils.email_service import send_user_invitation


company_bp = Blueprint('company_bp', __name__)


@company_bp.route('/', methods=['GET'])
@json_required()
@role_required()
def get_user_company(role):

    resp = JSONResponse(payload={
        "company": role.company.serialize_all()
    })
    return resp.to_json()


@company_bp.route('/', methods=['PUT'])
@json_required()
@role_required(level=0) #owner only
def update_company(role, body):

    to_update, invalids, msg = update_row_content(Company, body)
    if invalids:
        raise APIException.from_error(ErrorMessages(parameters=invalids, custom_msg=msg).bad_request)

    try:
        Company.query.filter(Company.id == role.company.id).update(to_update)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(message=f'Company updated').to_json()


@company_bp.route('/users', methods=['GET'])
@json_required()
@role_required(level=1)#andmin user
def get_company_users(role):

    roles = db.session.query(Role).join(Role.user).filter(Role._company_id == role.company.id).order_by(func.lower(User.fname).asc()).all()
    return JSONResponse(payload={
        "users": list(map(lambda x: {**x.user.serialize(), "role": x.serialize_all()}, roles))
    }).to_json()


@company_bp.route('/users', methods=['POST'])
@json_required({"email": str, "role_id": int})
@role_required(level=1)
def invite_user(role, body):

    email = body['email'].lower()
    
    valid, msg = validate_email(email)
    if not valid:
        raise APIException.from_error(ErrorMessages('email', custom_msg=msg).bad_request)

    new_role_function = RoleFunction.get_rolefunc_by_id(body['role_id'])
    if not new_role_function:
        raise APIException.from_error(ErrorMessages("role_id").notFound)

    if role.role_function.level > new_role_function.level:
        raise APIException.from_error(ErrorMessages("role_level").unauthorized)

    user = User.get_user_by_email(email)
    # nuevo usuario...
    if not user:
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
    
    if rel:
        raise APIException.from_error(
            ErrorMessages('email', custom_msg=f'User <{email}> is already listed in current company').conflict
        )
    
    sent, error = send_user_invitation(user_email=email, user_name=user.fname, company_name=role.company.name)
    if not sent:
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


@company_bp.route('/users/<int:user_id>', methods=['PUT'])
@json_required({'role_id':int, 'is_active':bool})
@role_required(level=1)
def update_user_company_relation(role, body, user_id):

    role_id = body['role_id']
    new_status = body['is_active']
    error = ErrorMessages()

    if user_id == role.user.id:
        error.parameters.append('role_id')
        error.custom_msg = "can't update self-user role"
        raise APIException.from_error(error.conflict)

    target_role = Role.get_relation_user_company(user_id, role.company.id)
    if not target_role:
        error.parameters.append('user_id')
    
    new_rolefunction = RoleFunction.get_rolefunc_by_id(role_id)
    if not new_rolefunction:
        error.parameters.append('role_id')

    if error.parameters:
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


@company_bp.route('/users/<int:user_id>', methods=['DELETE'])
@json_required()
@role_required(level=1)
def delete_user_company_relation(role, user_id):

    error = ErrorMessages()
    if user_id == role.user.id:
        error.parameters.append('role_id')
        error.custom_msg = "can't delete self-user role"
        raise APIException.from_error(error.conflict)

    target_role = Role.get_relation_user_company(user_id, role.company.id)
    if not target_role:
        raise APIException.from_error(ErrorMessages('user_id').notFound)

    try:
        db.session.delete(target_role)
        db.session.commit()

    except IntegrityError as ie:
        error.custom_msg = f"can't delete user-id: {user_id} relation - {ie}"
        raise APIException.from_error(error.conflict)

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse("user-relation was deleted of company").to_json()


@company_bp.route('/roles', methods=['GET'])
@json_required()
@role_required()#any user
def get_company_roles(role):

    return JSONResponse(payload={
        "roles": list(map(lambda x: x.serialize(), db.session.query(RoleFunction).all()))
    }).to_json()


@company_bp.route('/providers', methods=['GET'])
@json_required()
@role_required(level=1)
def get_company_providers(role):
    
    provider_id = request.args.get('provider_id', None)

    if not provider_id:
        page, limit = get_pagination_params()
        providers = role.company.providers.paginate(page, limit)

        return JSONResponse(payload={
            'providers': list(map(lambda x: x.serialize(), providers.items)),
            **pagination_form(providers)
        }).to_json()
    
    #provider_id in url parameters
    provider = role.company.get_provider(provider_id)
    if not provider:
        raise APIException.from_error(ErrorMessages(parameters='provider_id').notFound)

    return JSONResponse(
        payload={'provider': provider.serialize_all()}
    ).to_json()


@company_bp.route('/providers', methods=['POST'])
@json_required({'name': str})
@role_required(level=1)
def create_provider(role, body):

    error = ErrorMessages()

    to_add, invalids, msg = update_row_content(Provider, body)

    if invalids:
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


@company_bp.route('/providers/<int:provider_id>', methods=['PUT'])
@json_required()
@role_required(level=1)
def update_provider(role, body, provider_id):

    error = ErrorMessages()
    provider = role.company.get_provider(provider_id)
    if not provider:
        error.parameters.append('provider_id')
        raise APIException.from_error(error.notFound)

    to_update, invalids, msg = update_row_content(Provider, body)
    if invalids:
        error.parameters.append(invalids)
        error.custom_msg = msg
        raise APIException.from_error(error.bad_request)

    try:
        db.session.query(Provider).filter(Provider.id == provider.id).update(to_update)
        db.session.commit()

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(message=f'provider-id: {provider_id} was updated').to_json()


@company_bp.route('/providers/<int:provider_id>', methods=['DELETE'])
@json_required()
@role_required(level=1)
def delete_provider(role, provider_id):

    error = ErrorMessages(parameters="provider_id")
    provider = role.company.get_provider(provider_id)
    if not provider:
        raise APIException.from_error(error.notFound)

    try:
        db.session.delete(provider)
        db.session.commit()

    except IntegrityError as ie:
        error.custom_msg = f"can't delete provider_id: {provider_id} - {ie}"
        raise APIException.from_error(error.conflict)

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(message=f'provider-id: {provider_id} was deleted').to_json()


@company_bp.route('/categories', methods=['GET'])
@json_required()
@role_required()
def get_company_categories(role):

    category_id = request.args.get('category_id', None)

    if not category_id:
        cat = role.company.categories.filter(Category.parent_id == None).order_by(Category.name.asc()).all() #root categories only
        
        return JSONResponse(
            message="ok",
            payload={
                "categories": list(map(lambda x: x.serialize_children(), cat))
            }
        ).to_json()

    #category-id is present in the url-parameters
    cat = role.company.get_category_by_id(category_id)
    if not cat:
        raise APIException.from_error(ErrorMessages("category_id").notFound)

    #return item
    return JSONResponse(
        message="ok",
        payload={
            'category': cat.serialize_all()
        }
    ).to_json()


@company_bp.route('/categories', methods=['POST'])
@company_bp.route('/categories/<int:category_id>', methods=['PUT'])
@json_required({'name': str})
@role_required()
def create_or_update_category(role, body, category_id=None):

    parent_id = body.get('parent_id', None)
    new_name = body.get('name', '').lower()
    error = ErrorMessages()

    if parent_id:
        parent = role.company.get_category_by_id(parent_id)
        if not parent:
            error.parameters.append('parent_id')
            raise APIException.from_error(error.notFound)

    category_exists = db.session.query(Category).select_from(Company).join(Company.categories).\
        filter(Company.id == role.company.id, func.lower(Company.name) == new_name).first()

    if category_exists:
        error.parameters.append('name')
        error.custom_msg = f'category name: {new_name} already exists'
        raise APIException.from_error(error.conflict)

    to_add, invalids, msg = update_row_content(Category, body)
    if invalids:
        error.parameters.append(invalids)
        error.custom_msg = msg
        raise APIException.from_error(error.bad_request)

    if not category_id:
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
    if not target_cat:
        error.parameters.append('category_id')
        raise APIException.from_error(error.notFound)

    try:
        db.session.query(Category).filter(Category.id == target_cat.id).update(to_add)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f'category-id: {category_id} updated').to_json()


@company_bp.route('/categories/<int:cat_id>/attributes', methods=['GET'])
@json_required()
@role_required()
def get_category_attributes(role, cat_id):

    error = ErrorMessages()
    target_cat = role.company.get_category_by_id(cat_id)
    if not target_cat:
        error.parameters.append('category_id')
        raise APIException.from_error(error.notFound)

    all_attributes = target_cat.get_attributes()
    
    payload = {
        'attributes': list(map(lambda x: x.serialize_all(), all_attributes))
    }

    return JSONResponse(
        payload=payload
    ).to_json()


@company_bp.route('/categories/<int:category_id>/attributes', methods=['PUT'])
@json_required({'attributes': list})
@role_required(level=1)
def update_category_attributes(role, body, category_id):

    error = ErrorMessages()
    attributes = body.get('attributes')
    target_cat = role.company.get_category_by_id(category_id)

    if not target_cat:
        error.parameters.append('category_id')
        raise APIException.from_error(error.notFound)

    if not attributes: #empty list clear all attibutes
        try:
            target_cat.attributes = []
            db.session.commit()
        except SQLAlchemyError as e:
            handle_db_error(e)

        return JSONResponse(
            message=f'all attributes of category-id: {category_id} were deleted',
        ).to_json()

    not_integer = [r for r in attributes if not isinstance(r, int)]
    if not_integer:
        error.parameters.append('attributes')
        error.custom_msg = f'list of attributes must include integers values only.. <{not_integer}> were detected'
        raise APIException.from_error(error.bad_request)

    new_attributes = role.company.attributes.filter(Attribute.id.in_(attributes)).all()
    if not new_attributes:
        error.parameters.append('attributes')
        error.custom_msg = f'no attributes were found in the database'
        raise APIException.from_error(error.notFound)

    try:
        target_cat.attributes = new_attributes
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message=f'category-id: {category_id} updated',
        payload={
            'category': target_cat.serialize()
        }
    ).to_json()


@company_bp.route('/categories/<int:category_id>', methods=['DELETE'])
@json_required()
@role_required()
def delete_category(role, category_id=None):

    error = ErrorMessages(parameters="category_id")
    cat = role.company.get_category_by_id(category_id)
    if not cat:
        raise APIException.from_error(error.notFound)

    try:
        db.session.delete(cat)
        db.session.commit()

    except IntegrityError as ie:
        error.custom_msg = f"can't delete category_id:{category_id} - {ie}"
        raise APIException.from_error(error.conflict)

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f"Category id: <{category_id}> has been deleted").to_json()


@company_bp.get('/item-attributes')
@json_required()
@role_required()
def get_company_attributes(role):

    attribute_id = request.args.get('attribute_id', None)
    if not attribute_id:

        page, limit = get_pagination_params()
        name_like = request.args.get('like', '').lower()

        attributes = role.company.attributes.filter(func.lower(Attribute.name).like(f'%{name_like}%')).\
            order_by(Attribute.name.asc()).paginate(page, limit)

        return JSONResponse(
            payload={
                'attributes': list(map(lambda x:x.serialize(), attributes.items)),
                **pagination_form(attributes)
            }
        ).to_json()

    error = ErrorMessages(parameters='attribute_id')
    target_attr = role.company.get_attribute(attribute_id)
    if not target_attr:
        raise APIException.from_error(error.notFound)

    return JSONResponse(
        payload={
            'attribute': target_attr.serialize()
        }
    ).to_json()


@company_bp.post('/item-attributes')
@json_required({'name': str})
@role_required(level=1)    
def create_attribute(role, body):

    error = ErrorMessages()
    attribute_exists = db.session.query(Attribute).select_from(Company).join(Company.attributes).\
        filter(func.lower(Attribute.name) == body['name'].lower()).first()
        
    if attribute_exists:
        error.parameters.append('name')
        error.custom_msg = f"attribute <{body['name']}> already exists"
        raise APIException.from_error(error.conflict)
        
    to_add, invalids, msg = update_row_content(Attribute, body)

    if invalids:
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


@company_bp.put('/item-attributes/<int:attribute_id>')
@json_required({'name': str})
@role_required(level=1)
def update_attribute(role, body, attribute_id):

    error = ErrorMessages()
    target_attr = role.company.get_attribute(attribute_id)
    if not target_attr:
        error.parameters.append('attribute_id')
        raise APIException.from_error(error.notFound)

    attribute_exists = db.session.query(Attribute).select_from(Company).join(Company.attributes).\
        filter(func.lower(Attribute.name) == body['name'].lower()).first()
        
    if attribute_exists:
        error.parameters.append('name')
        error.custom_msg = f"attribute <{body['name']}> already exists"
        raise APIException.from_error(error.conflict)

    to_update, invalids, msg = update_row_content(Attribute, body)
    if invalids:
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


@company_bp.delete('/item-attributes/<int:attribute_id>')
@json_required()
@role_required(level=1)
def delete_attribute(role, attribute_id):

    error = ErrorMessages(parameters="attribute_id")
    target_attr = role.company.get_attribute(attribute_id)
    if not target_attr:
        raise APIException.from_error(error.notFound)

    try:
        db.session.delete(target_attr)
        db.session.commit()
    
    except IntegrityError as ie:
        error.custom_msg = f"can't delete attribute_id: {attribute_id} - {ie}"
        raise APIException.from_error(error.conflict)

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f'attribute_id: {attribute_id} deleted').to_json()


@company_bp.get('/item-attributes/<int:attribute_id>/values')
@json_required()
@role_required()
def get_attribute_values(role, attribute_id):
    
    error = ErrorMessages(parameters='attribute_id')
    target_attr = role.company.get_attribute(attribute_id)
    if not target_attr:
        raise APIException.from_error(error.notFound)

    #get url parameters
    page, limit = get_pagination_params()
    name_like = request.args.get('name_like', '').lower()
    
    values = target_attr.attribute_values.filter(func.lower(AttributeValue.value).like(f'%{name_like}%')).\
        order_by(AttributeValue.value.asc()).paginate(page, limit)
    
    payload = {
        'attribute': target_attr.serialize(),
        'values': list(map(lambda x: x.serialize(), values.items)),
        **pagination_form(values)
    }

    return JSONResponse(
        payload=payload,
        message='ok'
    ).to_json()


@company_bp.post('/item-attributes/<int:attribute_id>/values')
@json_required({'attribute_value': str})
@role_required(level=1) 
def create_attribute_value(role, body, attribute_id):

    error = ErrorMessages()
    new_value = normalize_string(body['attribute_value'], spaces=True)
    if not new_value: #empty string
        error.parameters.append('attribute_value')
        error.custom_msg = 'attribute_value is invalid, empty string has been received'
        raise APIException.from_error(error.bad_request)

    target_attr = role.company.get_attribute(attribute_id)
    if not target_attr:
        error.parameters.append('attribute_id')
        raise APIException.from_error(error.notFound)

    value_exists = target_attr.attribute_values.filter(func.lower(AttributeValue.value) == new_value.lower()).first()
    if value_exists:
        error.parameters.append('attribute_value')
        error.custom_msg = f'<attribute_value: {new_value} already exists>'
        raise APIException.from_error(error.conflict)

    new_attr_value = AttributeValue(
        value = new_value,
        attribute_id = attribute_id
    )

    try:
        db.session.add(new_attr_value)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message= f'new value created for attribute_id: {attribute_id}',
        payload= {
            'attribute': target_attr.serialize(),
            'new_value': new_attr_value.serialize()
        },
        status_code=201
    ).to_json()


@company_bp.put('/item-attributes/values/<int:value_id>')
@json_required({'attribute_value': str})
@role_required(level=1)
def update_attribute_value(role, body, value_id):

    error = ErrorMessages()
    valid_id = validate_id(value_id)
    new_value = normalize_string(body['attribute_value'], spaces=True)
    if not new_value: #empty string
        error.parameters.append('attribute_value')
        error.custom_msg = 'attribute_value is invalid, empty string detected'
        raise APIException.from_error(error.bad_request)

    base_q = db.session.query(AttributeValue).select_from(Company).join(Company.attributes).join(Attribute.attribute_values).\
        filter(Company.id == role.company.id)

    value_exists = base_q.filter(func.lower(AttributeValue.value) == new_value.lower()).first()
    if value_exists:
        error.parameters.append('attribute_value')
        error.custom_msg = f'<attribute_value: {new_value} already exists>'
        raise APIException.from_error(error.conflict)

    target_value = base_q.filter(AttributeValue.id == valid_id).first()
    if not target_value:
        error.parameters.append('value_id')
        raise APIException.from_error(error.notFound)
    
    try:
        target_value.value = new_value
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message=f'attribute_value_id: <{value_id} updated>'
    ).to_json()


@company_bp.delete('/item-attributes/values/<int:value_id>')
@json_required()
@role_required(level=1)
def delete_attributeValue(role, value_id):

    error = ErrorMessages(parameters='value_id')
    valid_id = validate_id(value_id)

    target_value = db.session.query(AttributeValue).select_from(Company).join(Company.attributes).join(Attribute.attribute_values).\
        filter(Company.id == role.company.id, AttributeValue.id == valid_id).first()

    if not target_value:
        raise APIException.from_error(error.notFound)

    try:
        db.session.delete(target_value)
        db.session.commit()

    except IntegrityError as ie:
        error.custom_msg = f"can't delete value_id:{value_id} - {ie}"

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message=f'attribute_value_id: {value_id} deleted'
    ).to_json()