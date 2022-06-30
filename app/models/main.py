import logging
import string
from app.extensions import db
from datetime import datetime
from random import sample

from werkzeug.security import generate_password_hash
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import backref
from sqlalchemy import func

#utils
from app.utils.helpers import datetime_formatter, DefaultContent, normalize_datetime
from app.utils.validations import validate_id

#models
from .global_models import *
from .assoc_models import item_provider, attribute_category, attributeValue_item

logger = logging.getLogger(__name__)

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    _email = db.Column(db.String(256), unique=True, nullable=False)
    _password_hash = db.Column(db.String(256), nullable=False)
    _registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    _email_confirmed = db.Column(db.Boolean)
    _signup_completed = db.Column(db.Boolean)
    _image = db.Column(db.String(256), default=DefaultContent().user_image)
    fname = db.Column(db.String(128), default='')
    lname = db.Column(db.String(128), default='')
    phone = db.Column(db.String(32), default='')
    #relations
    roles = db.relationship('Role', back_populates='user', lazy='dynamic')
    p_orders = db.relationship('PurchaseOrder', back_populates='user', lazy='dynamic')

    def __repr__(self):
        return f"User(email={self.email})"

    @property
    def image(self):
        return self._image

    def serialize(self) -> dict:
        return {
            "id": self.id,
            "fname" : self.fname,
            "lname" : self.lname,
            "image": self.image,
            "email": self.email
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            "since": datetime_formatter(self._registration_date),
            "phone": self.phone,
        }

    def serialize_public_info(self) -> dict:
        return {
            'companies': list(map(lambda x: {'name': x.company.name, 'id': x.company.id}, filter(lambda x: x._isActive, self.roles))),
            'email_confirmed': self._email_confirmed,
            'signup_completed': self._signup_completed
        }
    
    def get_owned_company(self):
        """function to get company owned by user instance"""
        return self.roles.join(Role.role_function).filter(RoleFunction.code == 'owner').first()

    def filter_by_company_id(self, company_id=None):
        """get user role on the company_id"""
        comp_id = validate_id(company_id)
        if comp_id == 0:
            return None
        return self.roles.join(Role.company).filter(Company.id == comp_id).first()

    @classmethod
    def get_user_by_email(cls, email:str):
        """get user in the database by email"""
        return db.session.query(cls).filter(cls._email == email.lower()).first()

    @classmethod
    def get_user_by_id(cls, _id):
        """
        get user in the database by id
        - id parameter must be a positive integer value
        """
        valid = validate_id(_id)
        if valid == 0:
            return None
        return db.session.query(cls).get(valid)

    @property
    def password(self):
        raise AttributeError('Cannot view password')

    @password.setter
    def password(self, password):
        self._password_hash = generate_password_hash(password, method='sha256')

    @property
    def email(self):
        return self._email

    @email.setter
    def email(self, raw_email:str):
        self._email = raw_email.lower().strip()


class Role(db.Model):
    def __init__(self, *args, **kwargs) -> None:
        """update kwargs arguments with the last qr_code counter"""
        company_id = kwargs.get("_company_id", None)
        if not company_id:
            raise AttributeError("_company_id not found in kwargs parameters")
        
        last_role = db.session.query(Role).filter(Role._company_id == company_id).\
            order_by(Role._correlative.desc()).first()
        if not last_role:
            kwargs.update({"_correlative": 1})
        else:
            kwargs.update({"_correlative": last_role._correlative+1})

        super().__init__(*args, **kwargs)

    __tablename__ = 'role'
    id = db.Column(db.Integer, primary_key=True)
    _relation_date = db.Column(db.DateTime, default=datetime.utcnow)
    _company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    _user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    _role_function_id = db.Column(db.Integer, db.ForeignKey('role_function.id'), nullable=False)
    _isActive = db.Column(db.Boolean, default=True)
    _correlative = db.Column(db.Integer, default=0)
    #relations
    user = db.relationship('User', back_populates='roles', lazy='joined')
    company = db.relationship('Company', back_populates='roles', lazy='joined')
    role_function = db.relationship('RoleFunction', back_populates='roles', lazy='joined')

    def __repr__(self) -> str:
        return f'Role(id={self.id})'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'relation_date': datetime_formatter(self._relation_date),
            'is_active': self._isActive,
            'correlative': self._correlative
        }
    
    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            **self.role_function.serialize()
        }

    @classmethod
    def get_role_by_id(cls, _id):
        """get Role instance by id"""
        role_id = validate_id(_id)
        if role_id == 0:
            return None

        return db.session.query(cls).get(role_id)

    @classmethod
    def get_relation_user_company(cls, user_id, company_id):
        """return role between an user and company"""
        u_id = validate_id(user_id)
        c_id = validate_id(company_id)
        if u_id == 0 or c_id == 0:
            return None

        return db.session.query(cls).join(cls.user).join(cls.company).\
            filter(User.id==u_id, Company.id==c_id).first()


class Company(db.Model):
    __tablename__ = 'company'
    id = db.Column(db.Integer, primary_key=True)
    _creation_date = db.Column(db.DateTime, default=datetime.utcnow)
    _plan_id = db.Column(db.Integer, db.ForeignKey('plan.id'), nullable=False)
    _logo = db.Column(db.String(256), default=DefaultContent().company_image)
    name = db.Column(db.String(128), nullable=False)
    tz_name = db.Column(db.String(128), default="america/caracas")
    address = db.Column(JSON, default={'address': {}})
    currency = db.Column(JSON, default={"currency": DefaultContent().currency})
    #relationships
    plan = db.relationship('Plan', back_populates='companies', lazy='joined')
    roles = db.relationship('Role', back_populates='company', lazy='dynamic')
    storages = db.relationship('Storage', back_populates='company', lazy='dynamic')
    items = db.relationship('Item', back_populates='company', lazy='dynamic')
    categories = db.relationship('Category', back_populates='company', lazy='dynamic')
    providers = db.relationship('Provider', back_populates='company', lazy='dynamic')
    attributes = db.relationship('Attribute', back_populates='company', lazy='dynamic')
    qr_codes = db.relationship('QRCode', back_populates='company', lazy='dynamic')

    def __repr__(self) -> str:
        return f"Company(name={self.name})"

    @property
    def logo(self):
        return self._logo

    def serialize(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "logo": self.logo,
        }
    
    def serialize_all(self) -> dict:
        return{
            **self.serialize(),
            **self.currency,
            **self.address,
            'time_zone': self.tz_name,
            'storages': self.storages.count(),
            'items': self.items.count(),
        }

    def get_category_by_id(self, category_id):
        """get category instance related to self.id using category_id parameter"""
        valid = validate_id(category_id)
        if valid == 0:
            return None
        
        return self.categories.filter(Category.id == valid).first()

    def get_storage_by_id(self, storage_id):
        """get storage instance related to current company instance, using identifier"""
        valid = validate_id(storage_id)
        if valid == 0:
            return None

        return self.storages.filter(Storage.id == valid).first()

    def get_item_by_id(self, item_id):
        """get item instance related with current company, using identifier"""
        valid = validate_id(item_id)
        if valid == 0:
            return None

        return self.items.filter(Item.id == valid).first()

    def get_provider(self, provider_id):
        valid = validate_id(provider_id)
        if valid == 0:
            return None
        
        return self.providers.filter(Provider.id == valid).first()

    def get_attribute(self, att_id):
        valid = validate_id(att_id)
        if valid == 0:
            return None

        return self.attributes.filter(Attribute.id == valid).first()


class Storage(db.Model):
    __tablename__ = 'storage'
    id = db.Column(db.Integer, primary_key=True)
    _company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(128), nullable=True)
    code = db.Column(db.String(64), default = '')
    address = db.Column(JSON, default={'address': {}})
    latitude = db.Column(db.Float(precision=6), default=0.0)
    longitude = db.Column(db.Float(precision=6), default=0.0)
    #relations
    company = db.relationship('Company', back_populates='storages', lazy='joined')
    containers = db.relationship('Container', back_populates='storage', lazy='dynamic')
    stock = db.relationship('Stock', back_populates='storage', lazy='dynamic')

    def __repr__(self) -> str:
        return f'Storage(name={self.name})'

    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'code': f'{self.name[:3]}.{self.id:02d}' if self.code == '' else f'{self.code}.{self.id:02d}',
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            **self.address,
            'utc': {
                "latitude": self.latitude, 
                "longitude": self.longitude
            },
            'managed_items': self.stock.count(),
            'containers-count': self.containers.count()
        }

    def get_container(self, container_id:int):
        """get container instance by its id"""
        valid = validate_id(container_id)
        if valid == 0:
            return None

        return self.containers.filter(Container.id == valid).first()


class Item(db.Model):
    __tablename__='item'
    id = db.Column(db.Integer, primary_key=True)
    _company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    _images = db.Column(JSON, default={'images': [DefaultContent().item_image]})
    name = db.Column(db.String(128), nullable=False)
    sku = db.Column(db.String(64), default='')
    description = db.Column(db.Text)
    unit = db.Column(db.String(128))
    sale_price = db.Column(db.Float(precision=2), default=0.0)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    #relations
    company = db.relationship('Company', back_populates='items', lazy='select')
    stock = db.relationship('Stock', back_populates='item', lazy='dynamic')
    category = db.relationship('Category', back_populates='items', lazy='joined')
    providers = db.relationship('Provider', secondary=item_provider, back_populates='items', lazy='dynamic')
    attribute_values = db.relationship('AttributeValue', secondary=attributeValue_item, back_populates='items', lazy='dynamic')
    orders = db.relationship('Order', back_populates='item', lazy='dynamic')

    def __repr__(self) -> str:
        return f'Item(name={self.get_sku})'

    @property
    def get_sku(self):
        return f'{self.category.name[:5]}.{self.name[:5]}.id:{self.id:04d}'.replace(" ", "").lower() if not self.sku else f'{self.sku}.id:{self.id:04d}'.replace(" ", "").lower()

    @property
    def images(self):
        return self._images

    def serialize(self) -> dict:
        return {
            **self.images,
            'id': self.id,
            'name': self.name,
            'description': self.description or "",
            'sku': self.get_sku
        }

    def serialize_attributes(self) -> dict:
        attributes = self.category.get_attributes()
        return {
            'attributes': list(map(lambda x:x.serialize_with_item(self.id), attributes))
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            **self.serialize_attributes(),
            'unit': self.unit,
            'sale-price': self.sale_price,
            'category': {**self.category.serialize(), "path": self.category.serialize_path()} if self.category else {}
        }


class Category(db.Model):
    __tablename__= 'category'
    id = db.Column(db.Integer, primary_key=True)
    _company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    #relations
    children = db.relationship('Category', cascade="all, delete-orphan", backref=backref('parent', remote_side=id))
    company = db.relationship('Company', back_populates='categories', lazy='select')
    items = db.relationship('Item', back_populates='category', lazy='dynamic')
    attributes = db.relationship('Attribute', secondary=attribute_category, back_populates='categories', lazy='select')

    
    def __repr__(self) -> str:
        return f'Category(name={self.name})'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'name': self.name
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            "path": self.serialize_path(), 
            "sub-categories": list(map(lambda x: x.serialize(), self.children)),
            "attributes": list(map(lambda x: x.serialize(), self.get_attributes()))
        }

    def serialize_children(self) -> dict:
        return {
            **self.serialize(),
            "sub_categories": list(map(lambda x: x.serialize_children(), self.children))
        }

    def serialize_path(self) -> list:
        """serialize the path to root of current category"""
        path = []
        p = self.parent
        while p is not None:
            path.insert(0, f'name:{p.name}-id:{p.id}')
            p = p.parent
        
        return path

    def get_all_nodes(self) -> list:
        """get all children nodes of current category. Includes all descendants"""
        ids = [self.id]
        for i in self.children:
            ids.append(i.id)
            if i.children:
                ids.extend(i.get_all_nodes())
        
        return list(set(ids))

    def get_attributes(self, return_cat_ids:bool=False) -> list:
        """function that returns a list with all the attributes of the current category and its ascendat categories"""
        ids = [self.id]
        p = self.parent
        while p is not None:
            ids.append(p.id)
            if p.parent is not None:
                ids.append(p.parent_id)
            p = p.parent
        
        if return_cat_ids:
            return ids

        return db.session.query(Attribute).join(Attribute.categories).filter(Category.id.in_(ids)).all()

    def get_attribute_by_id(self, att_id):
        valid = validate_id(att_id)
        if valid == 0:
            return None

        self.attributes.filter(Attribute.id == valid).first()


class Provider(db.Model):
    __tablename__='provider'
    id = db.Column(db.Integer, primary_key=-True)
    _company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    contacts = db.Column(JSON, default={'contacts': []})
    address = db.Column(JSON, default={'address': {}})
    #relations
    company = db.relationship('Company', back_populates='providers', lazy='select')
    items = db.relationship('Item', secondary=item_provider, back_populates='providers', lazy='dynamic')
    acquisitions = db.relationship('Acquisition', back_populates='provider', lazy='dynamic')

    def __repr__(self) -> str:
        return f'Provider(name={self.name})'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'name': self.name
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            **self.contacts,
            **self.address,
            'acquisitions': self.acquisitions.count()
        }


class Container(db.Model):
    __tablename__ = 'container'
    id = db.Column(db.Integer, primary_key=True)
    _storage_id = db.Column(db.Integer, db.ForeignKey('storage.id'), nullable=False)
    _qr_code_id = db.Column(db.Integer, db.ForeignKey('qr_code.id'))
    code = db.Column(db.String(64), default='')
    description = db.Column(db.Text)
    location_description = db.Column(db.Text)
    #relations
    storage = db.relationship('Storage', back_populates='containers', lazy='joined')
    inventories = db.relationship('Inventory', back_populates='container', lazy='dynamic')
    qr_code = db.relationship('QRCode', back_populates='container', lazy='joined')

    def __repr__(self) -> str:
        return f'Container(id={self.id})'

    @property
    def get_code(self):
        return f'cont.id:{self.id}' if not self.code else f'{self.code}.id:{self.id}'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'code': self.get_code,
            'qr_code': self.qr_code.serialize() if self._qr_code_id else {},
            'description': self.description,
            'location': self.location_description
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            'items_contained': self.inventories.count()
        }


class Stock(db.Model):
    __tablename__ = 'stock'
    id = db.Column(db.Integer, primary_key=True)
    _storage_id = db.Column(db.Integer, db.ForeignKey('storage.id'), nullable=False)
    _item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    max = db.Column(db.Float(precision=2), default=1.0)
    min = db.Column(db.Float(precision=2), default=0.0)
    method = db.Column(db.String(64), default='FIFO')
    #relations
    item = db.relationship('Item', back_populates='stock', lazy='select')
    storage = db.relationship('Storage', back_populates='stock', lazy='select')
    acquisitions = db.relationship('Acquisition', back_populates='stock', lazy='dynamic')

    def __repr__(self) -> str:
        return f'Stock(id={self.id})'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'storage-limits': {'max': self.max, 'min': self.min},
            'method': self.method,
            'actual_value': self.get_stock_value()
        }

    @classmethod
    def get_stock(cls, item_id:int, storage_id:int):
        i_id = validate_id(item_id)
        s_id = validate_id(storage_id)
        if i_id == 0 or s_id == 0:
            return None

        return db.session.query(cls).join(cls.item).join(cls.storage).filter(Item.id == i_id, Storage.id == s_id).first()

    def get_stock_value(self) -> float:
        #todas las adquisiciones que se encuentran en el inventario.
        acquisitions = db.session.query(func.sum(Acquisition.item_qtty)).select_from(Stock).\
            join(Stock.acquisitions).join(Acquisition.inventories).\
                filter(Stock.id == self.id).scalar() or 0

        #todas las requisiciones validadas, es decir, con pago verificado o aprobados por el administrador.
        requisitions = db.session.query(func.sum(Requisition.item_qtty)).select_from(Stock).\
            join(Stock.acquisitions).join(Acquisition.inventories).join(Inventory.requisitions).\
                filter(Stock.id == self.id, Requisition._isValid == True).scalar() or 0
                
        return float(acquisitions - requisitions)


class PurchaseOrder(db.Model):
    __tablename__ = 'purchase_order'
    id = db.Column(db.Integer, primary_key=True)
    _user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False) #client
    _creation_date = db.Column(db.DateTime, default=datetime.utcnow)
    _payment_confirmed = db.Column(db.Boolean, default=False)
    _payment_date = db.Column(db.DateTime)
    _shipping_date = db.Column(db.DateTime)
    shipped_to = db.Column(db.String(128)) #person receiving the shipment
    shipping_address = db.Column(JSON, default={'address': {}})
    #relations
    user = db.relationship('User', back_populates='p_orders', lazy='select')
    orders = db.relationship('Order', back_populates='p_order', lazy='dynamic')

    def __repr__(self) -> str:
        return f'PurchasOrder(id={self.id})'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'code': f'PO-{self.id:04d}-{self._creation_date.strftime("%m.%Y")}',
            'created_date': datetime_formatter(self._creation_date),
            'payment_confirmed': self._payment_confirmed,
            'completed': True if self._shipping_date is not None else False
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            'payment_date': self._payment_confirmed or '',
            'shipping_date': self._shipping_date or '',
            'shipped_to': self.shipped_to,
            'shipping_address': self.shipping_address
        }


class Order(db.Model):
    __tablename__ = 'order'
    id = db.Column(db.Integer, primary_key=True)
    _purchase_order_id = db.Column(db.Integer, db.ForeignKey('purchase_order.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    item_qtty = db.Column(db.Float(precision=2), default=1.0)
    #relations
    item = db.relationship('Item', back_populates='orders', lazy='select')
    requisitions = db.relationship('Requisition', back_populates='order', lazy='dynamic')
    p_order = db.relationship('PurchaseOrder', back_populates='orders', lazy='select')

    def __repr__(self) -> str:
        return f'Order(id={self.id})'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'item_qtty': self.item_qtty
        }


class Requisition(db.Model):
    __tablename__ = 'requisition'
    id = db.Column(db.Integer, primary_key=True)
    _log = db.Column(JSON)
    _date_created = db.Column(db.DateTime, default=datetime.utcnow)
    _order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    _isCompleted = db.Column(db.Boolean, default=False)
    _isValidated = db.Column(db.Boolean, default=False)
    _isCancelled = db.Column(db.Boolean, default=False)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.id'), nullable=False)
    item_qtty = db.Column(db.Float(precision=2), default=1.0)
    #relations
    order = db.relationship('Order', back_populates='requisitions', lazy='select')
    inventory = db.relationship('Inventory', back_populates='requisitions', lazy='select')

    def __repr__(self) -> str:
        return f'Requisition(id={self.id})'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'number': f'RQ-{self.id:04d}-{self._date_created.strftime("%m.%Y")}',
            'item-qtty': self.item_qtty
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            'log': self._log,
            'created_date': self._date_created,
            'isCompleted': self._isCompleted,
            'isValidated': self._isValidated,
            'isCancelled': self._isCancelled
        }


class Acquisition(db.Model):
    __tablename__ = 'acquisition'
    id = db.Column(db.Integer, primary_key=True)
    _entry_date = db.Column(db.DateTime, default=datetime.utcnow)
    _log = db.Column(JSON)
    _stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'), nullable=False)
    _review_img = db.Column(JSON) #imagenes de la revision de los items.
    item_qtty = db.Column(db.Float(precision=2), default=0.0)
    unit_cost = db.Column(db.Float(precision=2), default=0.0)
    purchase_ref_num = db.Column(db.String(128))
    provider_part_code = db.Column(db.String(128))
    pkg_weight = db.Column(db.Float(precision=2), default=0.0) #kg
    pkg_volume = db.Column(db.Float(precision=2), default=0.0) #cm3
    status = db.Column(db.String(32), default='in-review')
    provider_id = db.Column(db.Integer, db.ForeignKey('provider.id'))
    #relations
    stock = db.relationship('Stock', back_populates='acquisitions', lazy='select')
    inventories = db.relationship('Inventory', back_populates='acquisition', lazy='dynamic')
    provider = db.relationship('Provider', back_populates='acquisitions', lazy='select')


    def __repr__(self) -> str:
        return f'Acquisition(id={self.id})'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'status': self.status,
            'number': f'ACQ-{self.id:03d}-{self._entry_date.strftime("%m.%Y")}'
        }


class Attribute(db.Model):
    __tablename__ = 'attribute'
    id = db.Column(db.Integer, primary_key=True)
    _company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    # relations
    company = db.relationship('Company', back_populates='attributes', lazy='select')
    attribute_values = db.relationship('AttributeValue', back_populates='attribute', lazy='dynamic')
    categories = db.relationship('Category', secondary=attribute_category, back_populates='attributes', lazy='select')

    def __repr__(self) -> str:
        return f'Attribute(name={self.name})'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'field': self.name
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            'count-values': self.attribute_values.count()
        }

    def serialize_with_item(self, target_item) -> dict:
        attr_value = self.attribute_values.join(AttributeValue.items).filter(Item.id == target_item).first()
        rsp = {
            **self.serialize(),
            'value': {}
        }
        if attr_value:
            rsp.update({'value': attr_value.serialize()})

        return rsp


class AttributeValue(db.Model):
    __tablename__ = 'attribute_value'
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.String(64), default="") #unit value for a given attribute
    attribute_id = db.Column(db.Integer, db.ForeignKey('attribute.id'), nullable=False)
    #relations
    items = db.relationship('Item', secondary=attributeValue_item, back_populates='attribute_values', lazy='dynamic')
    attribute = db.relationship('Attribute', back_populates='attribute_values', lazy='joined')

    def __repr__(self) -> str:
        return f'AttributeValue(value={self.value}, attribute_id={self.attribute_id})'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'name': self.value
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            'attribute': self.attribute.serialize()
        }


class Inventory(db.Model):
    __tablename__ = 'inventory'
    id = db.Column(db.Integer, primary_key=True)
    _date_created = db.Column(db.DateTime, default=datetime.utcnow)
    _qr_code_id = db.Column(db.Integer, db.ForeignKey('qr_code.id'))
    item_qtty = db.Column(db.Float(precision=2), default=1.0)
    container_id = db.Column(db.Integer, db.ForeignKey('container.id'), nullable=False)
    acquisition_id = db.Column(db.Integer, db.ForeignKey('acquisition.id'), nullable=False)
    #relations
    container = db.relationship('Container', back_populates='inventories', lazy='joined')
    acquisition = db.relationship('Acquisition', back_populates='inventories', lazy='joined')
    requisitions = db.relationship('Requisition', back_populates='inventory', lazy='dynamic')
    qr_code = db.relationship('QRCode', back_populates='inventory', lazy="joined")

    def __repr__(self) -> str:
        return f'Inventory(id={self.id})'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'initial_value': self.item_qtty,
            'actual_value': self.get_actual_inventory(),
            'qr_code': self.qr_code.serialize() if self.qr_code_id else {}
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            'container': self.container.serialize(),
            'acquisition': self.acquisition.serialize(),
            'date_created': normalize_datetime(self._date_created),
            'total_requisitions': self.requisitions.count() #all requisitions posted, valids and invalids
        }

    def get_actual_inventory(self):
        inputs = self.item_qtty
        outputs = db.session.query(func.sum(Requisition.item_qtty)).select_from(Inventory).\
            join(Inventory.requisitions).filter(Inventory.id == self.id, Requisition._isValid == True).scalar() or 0

        return inputs - outputs


class QRCode(db.Model):
    def __init__(self, *args, **kwargs) -> None:
        """update kwargs arguments with the last qr_code counter"""
        company_id = kwargs.get("_company_id", None)
        if not company_id:
            raise AttributeError("_company_id not found in kwargs parameters")
        
        last_qr = db.session.query(QRCode._correlative).filter(QRCode._company_id == company_id).\
            order_by(QRCode._correlative.desc()).first()
        if not last_qr:
            kwargs.update({"_correlative": 1})
        else:
            kwargs.update({"_correlative": last_qr._correlative+1})

        super().__init__(*args, **kwargs)

    __tablename__ = 'qr_code'
    id = db.Column(db.Integer, primary_key=True)
    _date_created = db.Column(db.DateTime, default=datetime.utcnow)
    _company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    _random_name = db.Column(db.String(4), default="".join(sample(string.ascii_letters, 4)))
    _correlative = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    #relations
    company = db.relationship('Company', back_populates='qr_codes', lazy='select')
    inventory = db.relationship('Inventory', back_populates='qr_code', uselist=False, lazy='select')
    container = db.relationship('Container', back_populates='qr_code', uselist=False, lazy='select')

    def __repr__(self) -> str:
        return f'QRCode(id={self.id})'


    def serialize(self) -> dict:
        return {
            'date_created': self._date_created,
            'is_active': self.is_active,
            'text': f"QR{self.id:02d}{self._random_name}",
            'keys': f"{self._correlative:02d}.{self.id:02d}"
        }


    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            'inventory': self.inventory.serialize() or {},
            'container': self.container.serialize() or {}
        }


    def check_if_used(self) -> bool:
        """functions return True if the QRCode instance is already assigned, else return False"""
        if self.container_id or self.inventory_id:
            return True

        return False


    @staticmethod
    def parse_qr(raw_qrcode:str) -> int:
        """get qr-id value from a valid formatted qr-string
        parameters: raw_qrcode:str (valid formatted qr-string)

        returns int(0) if parser fails
        returns int(id) for valid formatted qr-string
        """
        try:
            _id = int(raw_qrcode.split('/')[-1][2:-4])
        except:
            return 0

        return _id


    @classmethod
    def get_qr_instance(cls, qr_id:int):
        """returns a QRCode instance of id=int(qr_id)"""
        valid = validate_id(qr_id)
        if not valid:
            return None
        
        return db.session.query(cls).filter(cls.id == valid).first()