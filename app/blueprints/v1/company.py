from crypt import methods
from flask import Blueprint, request
from app.models.global_models import RoleFunction

#extensions
from app.models.main import AttributeValue, Company, QRCode, User, Role, Provider, Category, Attribute
from app.extensions import db
from sqlalchemy.exc import SQLAlchemyError, IntegrityError
from sqlalchemy import func

#utils
from app.utils.exceptions import APIException
from app.utils.helpers import (
    ErrorMessages as EM, IntegerHelpers, JSONResponse, QueryParams, StringHelpers, Validations
)
from app.utils.route_decorators import json_required, role_required
from app.utils.db_operations import Unaccent, handle_db_error, update_row_content
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

    to_update, invalids = update_row_content(Company, body)
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

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
    """
    optional query parameters:
        ?page="pagination-page:str"
        ?limit="pagination-limit:str"
        ?status="role-status:str" -> status_options: active, disabled, pending
    """

    qp = QueryParams(request.args)
    status = qp.get_first_value("status")
    page, limit = qp.get_pagination_params()

    main_q = db.session.query(Role).join(Role.user).filter(Role.company_id == role.company.id)
    
    if status:
        if status == "active":
            main_q = main_q.filter(Role._isActive == True)
        elif status == "disabled":
            main_q = main_q.filter(Role._isActive == False)
        elif status == "pending":
            main_q = main_q.filter(Role._inv_accepted == False)

    roles = main_q.order_by(func.lower(User.fname).asc()).paginate(page, limit)

    return JSONResponse(
        message=qp.get_warings(),
        payload={
            "users": list(map(lambda x: {**x.user.serialize(), "role": x.serialize_all()}, roles.items)),
            **qp.get_pagination_form(roles)
        }).to_json()


@company_bp.route('/users', methods=['POST'])
@json_required({"email": str, "role_id": int})
@role_required(level=1)
def invite_user(role, body):

    email = StringHelpers(body["email"])
    role_id = body["role_id"]

    invalids = Validations.validate_inputs({
        "role_id": IntegerHelpers.is_valid_id(role_id),
        "email": email.is_valid_email()
    })
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    new_role_function = RoleFunction.get_rolefunc_by_id(role_id)
    if not new_role_function:
        raise APIException.from_error(EM({"role_id": f"id-{role_id} not found"}).notFound)

    if role.role_function.level > new_role_function.level:
        raise APIException.from_error(EM({"role_level": "greater authorization level is required"}).unauthorized)

    user = User.get_user_by_email(email.email_normalized)
    # nuevo usuario...
    if not user:
        success, mail_msg = send_user_invitation(user_email=email.email_normalized, company_name=role.company.name)
        if not success:
            raise APIException.from_error(EM(mail_msg).service_unavailable)

        try:
            new_user = User(
                email=email.email_normalized,
                password = StringHelpers.random_password()
            )
            new_role = Role(
                user = new_user,
                company_id = role.company_id,
                role_function = new_role_function
            )
            db.session.add_all([new_user, new_role])
            db.session.commit()
        except SQLAlchemyError as e:
            handle_db_error(e)

        return JSONResponse("new user invited", status_code=201).to_json()

    #ususario existente...
    rel = db.session.query(User).join(User.roles).join(Role.company).\
        filter(User.id == user.id, Company.id == role.company_id).first()
    
    if rel:
        raise APIException.from_error(
            EM({"email": f"user <{email.value}> is already listed in current company'"}).conflict
        )
    
    sent, mail_msg = send_user_invitation(user_email=email.email_normalized, user_name=user.fname, company_name=role.company.name)
    if not sent:
        raise APIException.from_error(EM(mail_msg).service_unavailable)
        
    try:
        new_role = Role(
            company_id = role.company_id,
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

    role_id = body["role_id"]
    new_status = body['is_active']

    invalids = Validations.validate_inputs({
        "role_id": IntegerHelpers.is_valid_id(role_id),
        "user_id": IntegerHelpers.is_valid_id(user_id)
    })
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    if role_id == role.user.id:
        raise APIException.from_error(EM({"role_id": "can't update self-user role"}).conflict)

    target_role = Role.get_relation_user_company(user_id, role.company.id)
    if not target_role:
        raise APIException.from_error(EM({"user_id": f"id-{user_id} not found"}).notFound)
    
    new_rolefunction = RoleFunction.get_rolefunc_by_id(role_id)
    if not new_rolefunction:
        raise APIException.from_error(EM({"role_id": "not found"}).notFound)

    if role.role_function.level > new_rolefunction.level:
        raise APIException.from_error(EM({"role_level": "greater authorization level required"}).unauthorized)
        
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

    valid, msg = IntegerHelpers.is_valid_id(user_id)
    if not valid:
        raise APIException.from_error(EM({"user_id": msg}).bad_request)

    if user_id == role.user.id:
        raise APIException.from_error(EM({"role_id": "can't delete self-user role"}).conflict)

    target_role = Role.get_relation_user_company(user_id, role.company.id)
    if not target_role:
        raise APIException.from_error(EM({"user_id": "not found"}).notFound)

    try:
        db.session.delete(target_role)
        db.session.commit()

    except IntegrityError as ie:
        raise APIException.from_error(EM({"delete": f"can't delete user-id: {user_id} relation - {ie}"}).conflict)

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
    
    qp = QueryParams(request.args)
    provider_id = qp.get_first_value("provider_id", as_integer=True)

    if not provider_id:
        main_q = role.company.providers
        name_like = StringHelpers(qp.get_first_value("name_like"))

        if name_like:
            main_q = main_q.filter(Unaccent(func.lower(Provider.name)).like(f"%{name_like.unaccent.lower()}%"))

        page, limit = qp.get_pagination_params()
        providers = main_q.paginate(page, limit)

        return JSONResponse(
            message=qp.get_warings(),
            payload={
            'providers': list(map(lambda x: x.serialize(), providers.items)),
            **qp.get_pagination_form(providers)
        }).to_json()
    
    #provider_id in url parameters
    valid, msg = IntegerHelpers.is_valid_id(provider_id)
    if not valid:
        raise APIException.from_error(EM({"provider_id": msg}).bad_request)

    provider = role.company.get_provider(provider_id)
    if not provider:
        raise APIException.from_error(EM({"provider_id": f"id-{provider_id} not found"}).notFound)

    return JSONResponse(
        message=qp.get_warings(),
        payload={'provider': provider.serialize_all()}
    ).to_json()


@company_bp.route('/providers', methods=['POST'])
@json_required({'name': str})
@role_required(level=1)
def create_provider(role, body):

    to_add, invalids = update_row_content(Provider, body)
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    to_add.update({'company_id': role.company.id}) #se agrega company

    new_provider = Provider(**to_add)
    try:
        db.session.add(new_provider)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message='new provider was created', 
        payload={'provider': new_provider.serialize_all()},
        status_code=201
    ).to_json()


@company_bp.route('/providers/<int:provider_id>', methods=['PUT'])
@json_required()
@role_required(level=1)
def update_provider(role, body, provider_id):

    valid, msg = IntegerHelpers.is_valid_id(provider_id)
    if not valid:
        raise APIException.from_error(EM({"provider_id": msg}).bad_request)

    provider = role.company.get_provider(provider_id)
    if not provider:
        raise APIException.from_error(EM({"provider_id": f"id-{provider_id} not found"}).notFound)

    to_update, invalids = update_row_content(Provider, body)
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

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

    valid, msg = IntegerHelpers.is_valid_id(provider_id)
    if not valid:
        raise APIException.from_error(EM({"provider_id": msg}).bad_request)
    
    target_provider = role.company.get_provider(provider_id)
    if not target_provider:
        raise APIException.from_error(EM({"provider_id": f"id-{provider_id} not found"}).notFound)

    try:
        db.session.delete(target_provider)
        db.session.commit()

    except IntegrityError as ie:
        raise APIException.from_error(EM({"provider_id": f"can't delete provider id-{provider_id}, {ie}"}).conflict)

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(message=f'provider-id: {provider_id} has been deleted').to_json()


@company_bp.route('/categories', methods=['GET'])
@json_required()
@role_required()
def get_company_categories(role):

    qp = QueryParams(request.args)
    category_id = qp.get_first_value("category_id", as_integer=True)

    if not category_id:
        cat = role.company.categories.filter(Category.parent_id == None).order_by(Category.name.asc()).all() #root categories only
        
        return JSONResponse(
            message=qp.get_warings(),
            payload={
                "categories": list(map(lambda x: x.serialize_children(), cat))
            }
        ).to_json()

    #category-id is present in the url-parameters
    valid, msg = IntegerHelpers.is_valid_id(category_id)
    if not valid:
        raise APIException.from_error(EM({"category_id": msg}).bad_request)

    cat = role.company.get_category_by_id(category_id)
    if not cat:
        raise APIException.from_error(EM({"category_id": f"id-{category_id} not found"}).notFound)

    #return item
    return JSONResponse(
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
    new_name = StringHelpers(body["name"])

    if parent_id:
        valid, msg = IntegerHelpers.is_valid_id(parent_id)
        if not valid:
            raise APIException.from_error(EM({"parent_id": msg}).bad_request)

        parent = role.company.get_category_by_id(parent_id)
        if not parent:
            raise APIException.from_error(EM({"parent_id": f"id-{parent_id} not found"}).notFound)

    newRows, invalids = update_row_content(Category, body)
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    main_q = db.session.query(Category).select_from(Company).join(Company.categories).\
        filter(Company.id == role.company.id, Unaccent(func.lower(Category.name)) == new_name.unaccent.lower())

    #POST method
    if request.method == "POST":
        category_exists = main_q.first()
        if category_exists:
            raise APIException.from_error(EM({"name": f"category name [{new_name.value}] already exists"}).conflict)

        newRows.update({'company_id': role.company.id, "parent_id": parent_id})
        new_category = Category(**newRows)

        try:
            db.session.add(new_category)
            db.session.commit()
        except SQLAlchemyError as e:
            handle_db_error(e)

        return JSONResponse(
            payload={"category": new_category.serialize()},
            status_code=201
        ).to_json()

    #PUT method
    target_cat = role.company.get_category_by_id(category_id)
    if not target_cat:
        raise APIException.from_error(EM({"category_id": f"id-{category_id} not found"}).notFound)

    name_exists = main_q.filter(Category.id != category_id).first()
    if name_exists:
        raise APIException.from_error(EM({"name": f"category name [{new_name.value}] already exists"}).conflict)

    try:
        db.session.query(Category).filter(Category.id == target_cat.id).update(newRows)
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f'category-id: {category_id} updated').to_json()


@company_bp.route("/categories/<int:cat_id>", methods=["DELETE"])
@json_required()
@role_required(level=1)
def delete_category(role, cat_id):

    valid, msg = IntegerHelpers.is_valid_id(cat_id)
    if not valid:
        raise APIException.from_error(EM({"cat_id": msg}).bad_request)

    target_cat = role.company.get_category_by_id(cat_id)
    if not target_cat:
        raise APIException.from_error(EM({"cat_id": f"id-{cat_id} not found"}).notFound)

    try:
        db.session.delete(target_cat)
        db.session.commit()
    
    except IntegrityError as ie:
        raise APIException.from_error(EM({"cat_id": f"can't delete category_id: {cat_id}, {ie}"}).conflict)

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message=f"category_id: {cat_id} has been deleted"
    ).to_json()


@company_bp.route('/categories/<int:cat_id>/attributes', methods=['GET'])
@json_required()
@role_required()
def get_category_attributes(role, cat_id):

    valid, msg = IntegerHelpers.is_valid_id(cat_id)
    if not valid:
        raise APIException.from_error(EM({"cat_id": msg}).bad_request)
    
    target_cat = role.company.get_category_by_id(cat_id)
    if not target_cat:
        raise APIException.from_error(EM({"cat_id": f"id-{cat_id} not found"}).notFound)

    all_attributes = target_cat.get_attributes()

    return JSONResponse(
        payload={'attributes': list(map(lambda x: x.serialize_all(), all_attributes))}
    ).to_json()


@company_bp.route('/categories/<int:category_id>/attributes', methods=['PUT'])
@json_required({'attributes': list})
@role_required(level=1)
def update_category_attributes(role, body, category_id):

    attributes = body.get('attributes')
    valid, msg = IntegerHelpers.is_valid_id(category_id)
    if not valid:
        raise APIException.from_error(EM({"category_id": msg}).bad_request)

    target_cat = role.company.get_category_by_id(category_id)
    if not target_cat:
        raise APIException.from_error(EM({"category_id": f"id-{category_id} not found"}).notFound)

    if not attributes: #empty list clear all attibutes
        try:
            target_cat.attributes = []
            db.session.commit()
        except SQLAlchemyError as e:
            handle_db_error(e)

        return JSONResponse(
            message=f'all attributes of category-id: {category_id} were removed',
        ).to_json()

    not_integer = [r for r in attributes if not isinstance(r, int)]
    if not_integer:
        raise APIException.from_error(EM(
            {"attributes": f"list of attributes must include integers values only.. <{not_integer}> were detected"}
        ).bad_request)

    new_attributes = role.company.attributes.filter(Attribute.id.in_(attributes)).all()
    if not new_attributes:
        raise APIException.from_error(EM({"attributes": "no attributes were found in the database"}).notFound)

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


@company_bp.route("/item-attributes", methods=["GET"])
@json_required()
@role_required()
def get_company_attributes(role):

    qp = QueryParams(request.args)
    attribute_id = qp.get_first_value("attribute_id", as_integer=True)

    if not attribute_id:
        page, limit = qp.get_pagination_params()
        name_like = StringHelpers(qp.get_first_value("name_like"))

        main_q = role.company.attributes.order_by(Attribute.name.asc())

        if name_like:
            main_q = main_q.filter(Unaccent(func.lower(Attribute.name)).like(f"%{name_like.unaccent.lower()}%"))

        attributes = main_q.paginate(page, limit)

        return JSONResponse(
            message=qp.get_warings(),
            payload={
                'attributes': list(map(lambda x:x.serialize(), attributes.items)),
                **qp.get_pagination_form(attributes)
            }
        ).to_json()

    valid, msg = IntegerHelpers.is_valid_id(attribute_id)
    if not valid:
        raise APIException.from_error(EM({"attribute_id": msg}).bad_request)
    
    target_attr = role.company.get_attribute(attribute_id)
    if not target_attr:
        raise APIException.from_error(EM({"attribute_id": f"id-{attribute_id} not found"}).notFound)

    return JSONResponse(
        message=qp.get_warings(),
        payload={
            'attribute': target_attr.serialize()
        }
    ).to_json()

#continue here down with the review

@company_bp.route('/item-attributes', methods=["POST"])
@json_required({'name': str})
@role_required(level=1)    
def create_attribute(role, body):

    name = StringHelpers(body["name"])
    attribute_exists = db.session.query(Attribute).select_from(Company).join(Company.attributes).\
        filter(Unaccent(func.lower(Attribute.name)) == name.unaccent.lower()).first()
        
    if attribute_exists:
        raise APIException.from_error(EM({"name": f"attribute <{name.value}> already exists"}).conflict)
        
    to_add, invalids = update_row_content(Attribute, body)

    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)
    
    to_add.update({'company_id': role.company.id})
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


@company_bp.route("/item-attributes/<int:attribute_id>", methods=["PUT"])
@json_required({'name': str})
@role_required(level=1)
def update_attribute(role, body, attribute_id):

    name = StringHelpers(body["name"])

    invalids = Validations.validate_inputs({
        "attribute_id": IntegerHelpers.is_valid_id(attribute_id),
        "name": name.is_valid_string()
    })
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    target_attr = role.company.get_attribute(attribute_id)
    if not target_attr:
        raise APIException.from_error(EM({"attribute_id": f"id-{attribute_id} not found"}).notFound)

    attribute_exists = db.session.query(Attribute).select_from(Company).join(Company.attributes).\
        filter(Unaccent(func.lower(Attribute.name)) == name.unaccent.lower()).first()
        
    if attribute_exists:
        raise APIException.from_error(EM({"name": f"attribute <{name.value}> already exists"}).conflict)

    to_update, invalids = update_row_content(Attribute, body)
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)
    
    try:
        db.session.query(Attribute).filter(Attribute.id == target_attr.id).update(to_update)
        db.session.commit()

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message=f'attribute-id: {attribute_id} updated'
    ).to_json()


@company_bp.route("/item-attributes/<int:attribute_id>", methods=["DELETE"])
@json_required()
@role_required(level=1)
def delete_attribute(role, attribute_id):

    valid, msg = IntegerHelpers.is_valid_id(attribute_id)
    if not valid:
        raise APIException.from_error(EM({"attribute_id": msg}).bad_request)

    target_attr = role.company.get_attribute(attribute_id)
    if not target_attr:
        raise APIException.from_error(EM({"attribute_id": f"id-{attribute_id} not found"}).notFound)

    try:
        db.session.delete(target_attr)
        db.session.commit()
    
    except IntegrityError as ie:
        raise APIException.from_error(EM({"attribute_id": f"can't delete attribute_id: {attribute_id} - {ie}"}).conflict)

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(f'attribute_id: {attribute_id} deleted').to_json()


@company_bp.route('/item-attributes/<int:attribute_id>/values', methods=["GET"])
@json_required()
@role_required()
def get_attribute_values(role, attribute_id):
    
    qp = QueryParams(request.args)
    valid, msg = IntegerHelpers.is_valid_id(attribute_id)
    if not valid:
        raise APIException.from_error(EM({"attribute_id": msg}).bad_request)

    target_attr = role.company.get_attribute(attribute_id)
    if not target_attr:
        raise APIException.from_error(EM({"attribute_id": f"id-{attribute_id} not found"}).notFound)

    main_q = target_attr.attribute_values.order_by(AttributeValue.value.asc())
    page, limit = qp.get_pagination_params()

    name_like = qp.get_first_value("name_like")
    if name_like:
        sh = StringHelpers(string=name_like)
        main_q = main_q.filter(Unaccent(func.lower(AttributeValue.value)).like(f'%{sh.unaccent.lower()}%'))

    main_q = main_q.paginate(page, limit)
    
    payload = {
        'attribute': target_attr.serialize(),
        'values': list(map(lambda x: x.serialize(), main_q.items)),
        **qp.get_pagination_form(main_q)
    }

    return JSONResponse(
        payload=payload,
        message=qp.get_warings()
    ).to_json()


@company_bp.route("/item-attributes/<int:attribute_id>/values", methods=["POST"])
@json_required({'attribute_value': str})
@role_required(level=1) 
def create_attribute_value(role, body, attribute_id):

    attr_value = StringHelpers(body["attribute_value"])
    invalids = Validations.validate_inputs({
        "attribute_value": attr_value.is_valid_string(),
        "attribute_id": IntegerHelpers.is_valid_id(attribute_id)
    })
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    target_attr = role.company.get_attribute(attribute_id)
    if not target_attr:
        raise APIException.from_error(EM({"attribute_id": f"id-{attribute_id} not found"}).notFound)
        
    value_exists = target_attr.attribute_values.\
        filter(Unaccent(func.lower(AttributeValue.value)) == attr_value.unaccent.lower()).first()
    if value_exists:
        raise APIException.from_error(EM({"attribute_value": f"attribute_value: {attr_value.value} already exists"}).conflict)


    new_attr_value = AttributeValue(
        value = attr_value.value,
        attribute = target_attr
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


@company_bp.route("/item-attributes/values/<int:value_id>", methods=["PUT"])
@json_required({'attribute_value': str})
@role_required(level=1)
def update_attribute_value(role, body, value_id):

    attr_value = StringHelpers(body["attribute_value"])
    invalids = Validations.validate_inputs({
        "attribute_value": attr_value.is_valid_string(),
        "value_id": IntegerHelpers.is_valid_id(value_id)
    })
    if invalids:
        raise APIException.from_error(EM(invalids).bad_request)

    base_q = db.session.query(AttributeValue).select_from(Company).join(Company.attributes).\
        join(Attribute.attribute_values).filter(Company.id == role.company.id)

    value_exists = base_q.filter(Unaccent(func.lower(AttributeValue.value)) == attr_value.unaccent.lower()).first()
    if value_exists:
        raise APIException.from_error(EM({"attribute_value": f"attribute_value: {attr_value.value} already exists"}).conflict)

    target_value = base_q.filter(AttributeValue.id == value_id).first()
    if not target_value:
        raise APIException.from_error(EM({"target_value": f"id-{value_id}"}).notFound)
    
    try:
        target_value.value = attr_value.value
        db.session.commit()
    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message=f'attribute_value_id: <{value_id} updated>'
    ).to_json()


@company_bp.route("/item-attributes/values/<int:value_id>", methods=["DELETE"])
@json_required()
@role_required(level=1)
def delete_attributeValue(role, value_id):

    valid, msg = IntegerHelpers.is_valid_id(value_id)
    if not valid:
        raise APIException.from_error(EM({"value_id": msg}).bad_request)

    target_value = db.session.query(AttributeValue).select_from(Company).join(Company.attributes).join(Attribute.attribute_values).\
        filter(Company.id == role.company.id, AttributeValue.id == value_id).first()

    if not target_value:
        raise APIException.from_error(EM({"value_id": f"id-{value_id} not found"}).notFound)

    try:
        db.session.delete(target_value)
        db.session.commit()

    except IntegrityError as ie:
        raise APIException.from_error(EM({"value_id": f"can't delete value_id:{value_id} - {ie}"}))

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message=f'attribute_value_id: {value_id} deleted'
    ).to_json()


@company_bp.route("/qrcodes", methods=["GET"])
@json_required()
@role_required()
def get_all_qrcodes(role):

    qp = QueryParams(request.args)
    page, limit = qp.get_pagination_params()
    qr_codes = role.company.qr_codes.paginate(page, limit)

    return JSONResponse(
        message=qp.get_warings(),
        payload={
            "qr_codes": list(map(lambda x:x.serialize(), qr_codes.items)),
            **qp.get_pagination_form(qr_codes)
        }
    ).to_json()


@company_bp.route("/qrcodes", methods=["POST"])
@json_required({"count": int})
@role_required()
def create_qrcode(role, body):

    count = body["count"]
    if count <= 0:
        raise APIException.from_error(EM({"count": f"count can't be less than 0"}).bad_request)

    bulk_qrcode = []
    while len(bulk_qrcode) < count:
        new_qrcode = QRCode(company_id = role.company.id)
        try:
            db.session.add(new_qrcode)
            db.session.commit()
        except SQLAlchemyError as e:
            handle_db_error(e)

        bulk_qrcode.append(new_qrcode)

    return JSONResponse(
        message="ok",
        payload={"qrcodes": list(map(lambda x:x.serialize(), bulk_qrcode))}
    ).to_json()


@company_bp.route("/qrcodes/<int:qrcode_id>", methods=["DELETE"])
@json_required()
@role_required()
def delete_qrcode(role, qrcode_id):

    valid, msg = IntegerHelpers.is_valid_id(qrcode_id)
    if not valid:
        raise APIException.from_error(EM({"qrcode_id": msg}).bad_request)

    target_qrcode = db.session.query(QRCode).join(QRCode.company).\
        filter(Company.id == role.company.id, QRCode.id == qrcode_id).first()

    if not target_qrcode:
        raise APIException.from_error(EM({"qrcode_id": f"id-{qrcode_id} not found"}).notFound)

    try:
        db.session.delete(target_qrcode)
        db.session.commit()

    except IntegrityError as ie:
        raise APIException.from_error(EM({"qrcode_ud": f"can't delete qrcode_id:{qrcode_id} - {ie}"}).conflict)

    except SQLAlchemyError as e:
        handle_db_error(e)

    return JSONResponse(
        message=f"qrcode_id: {qrcode_id} deleted"
    ).to_json()