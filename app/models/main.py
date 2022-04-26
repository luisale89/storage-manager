from email.policy import default
from app.extensions import db
from datetime import datetime

from werkzeug.security import generate_password_hash
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import backref
from sqlalchemy import func

from app.utils.helpers import datetime_formatter, DefaultContent

#models
from .global_models import *
from .assoc_models import item_provider, attribute_category

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    _email = db.Column(db.String(256), unique=True, nullable=False)
    _password_hash = db.Column(db.String(256), nullable=False)
    _registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    _email_confirmed = db.Column(db.Boolean)
    _status = db.Column(db.String(12))
    fname = db.Column(db.String(128), nullable=False)
    lname = db.Column(db.String(128), nullable=False)
    image = db.Column(db.String(256), default=DefaultContent().user_image)
    phone = db.Column(db.String(32), default="")
    #relations
    roles = db.relationship('Role', back_populates='user', lazy='joined')
    company = db.relationship('Company', back_populates='user', uselist=False, lazy='joined')

    def __repr__(self):
        return f"<User {self.id}>"

    def serialize(self) -> dict:
        return {
            "id": self.id,
            "fname" : self.fname,
            "lname" : self.lname,
            "image": self.image,
            "user-since": datetime_formatter(self._registration_date)
        }

    def serialize_employers(self) -> dict:
        return {
            'employers': list(map(lambda x: {
                **x.serialize(), 
                **x.company.serialize(), 
                **x.role_function.serialize()
            }, filter(lambda y: y.company is not None, self.roles))),
        }

    def serialize_company(self) -> dict:
        return self.company.serialize() if self.company is not None else {}

    def serialize_private(self) -> dict:
        return {
            "email": self._email,
            "phone": self.phone or ""
        }

    def check_if_user_exists(email) -> bool:
        return True if db.session.query(User).filter(User._email == email).first() else False

    @property
    def password(self):
        raise AttributeError('Cannot view password')

    @password.setter
    def password(self, password):
        self._password_hash = generate_password_hash(password, method='sha256')


class Role(db.Model):
    __tablename__ = 'role'
    id = db.Column(db.Integer, primary_key=True)
    _relation_date = db.Column(db.DateTime, default=datetime.utcnow)
    _company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    _user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    _relation_log = db.Column(JSON)
    role_function_id = db.Column(db.Integer, db.ForeignKey('role_function.id'), nullable=False)
    #relations
    user = db.relationship('User', back_populates='roles', lazy='joined')
    company = db.relationship('Company', back_populates='roles', lazy='joined')
    role_function = db.relationship('RoleFunction', back_populates='roles', lazy='joined')

    def __repr__(self) -> str:
        return f'<User {self.user_id} - Company {self._company_id} - Role {self._company_id}'

    def serialize(self) -> dict:
        return {
            'role-id': self.id,
            'relation-date': datetime_formatter(self._relation_date),
            'historics': self._relation_log
        }

class Company(db.Model):
    __tablename__ = 'company'
    id = db.Column(db.Integer, primary_key=True)
    _creation_date = db.Column(db.DateTime, default=datetime.utcnow)
    _plan_id = db.Column(db.Integer, db.ForeignKey('plan.id'), nullable=False)
    _user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    tax_id = db.Column(db.String(64))
    logo = db.Column(db.String(256), default=DefaultContent().company_image)
    currency = db.Column(db.Integer, default = 0)
    tz_name = db.Column(db.String(128), default="america/caracas")
    address = db.Column(JSON, default={})
    currencies = db.Column(JSON, default={"all": [DefaultContent().currency]})
    #relationships
    user = db.relationship('User', back_populates='company', lazy='select')
    plan = db.relationship('Plan', back_populates='companies', lazy='joined')
    roles = db.relationship('Role', back_populates='company', lazy='dynamic')
    storages = db.relationship('Storage', back_populates='company', lazy='dynamic')
    items = db.relationship('Item', back_populates='company', lazy='dynamic')
    categories = db.relationship('Category', back_populates='company', lazy='dynamic')
    thirds = db.relationship('Third', back_populates='company', lazy='dynamic')
    units_catalog = db.relationship('UnitCatalog', back_populates='company', lazy='dynamic')
    attributes_catalog = db.relationship('Attribute', back_populates='company', lazy='dynamic')

    def __repr__(self) -> str:
        return f"<Company {self.id}>"

    def serialize(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "address": self.address,
            "logo": self.logo,
            "currency": self.currencies.get('all', [DefaultContent().currency])[0],
            "time-zone-name": self.tz_name
        }


class Storage(db.Model):
    __tablename__ = 'storage'
    id = db.Column(db.Integer, primary_key=True)
    _company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(128), nullable=True)
    description = db.Column(db.Text)
    address = db.Column(JSON, default={})
    latitude = db.Column(db.Float(precision=6), default=0.0)
    longitude = db.Column(db.Float(precision=6), default=0.0)
    #relations
    company = db.relationship('Company', back_populates='storages', lazy='joined')
    shelves = db.relationship('Shelf', back_populates='storage', lazy='dynamic')
    stock = db.relationship('Stock', back_populates='storage', lazy='dynamic')

    def __repr__(self) -> str:
        return f'<Storage {self.name}>'

    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description or "",
            'address': self.address,
            'utc': {
                "latitude": self.latitude, 
                "longitude": self.longitude
            }
        }


class Item(db.Model):
    __tablename__='item'
    id = db.Column(db.Integer, primary_key=True)
    _company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    unit = db.Column(db.String(128))
    sale_price = db.Column(db.Float(precision=2), default=0.0)
    images = db.Column(JSON, default={'urls': [DefaultContent().item_image]})
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    #relations
    company = db.relationship('Company', back_populates='items', lazy='select')
    stock = db.relationship('Stock', back_populates='item', lazy='dynamic')
    category = db.relationship('Category', back_populates='items', lazy='joined')
    providers = db.relationship('Third', secondary=item_provider, back_populates='items', lazy='dynamic')
    attributes = db.relationship('ItemAttribute', back_populates='item', lazy='dynamic')
    orders = db.relationship('ItemInOrder', back_populates='item', lazy='dynamic')


    def __repr__(self) -> str:
        return f'<Item: {self.name}>'

    def serialize(self) -> dict:
        return {
            'name': self.name,
            'description': self.description or "",
            'sku': f'{self.category.name[:5]}-{self.id:04d}-cp.{self._company_id}'
        }

    def serialize_fav_image(self) -> dict:
        return {
            'image': self.images.get('urls', [DefaultContent().item_image])[0] #return first image in json object
        }

    def serialize_datasheet(self) -> dict:
        return {
            'unit': self.unit,
            'images': self.images.get('urls', [DefaultContent().item_image]), #return all images in json object
            'category': self.category.serialize() if self.category is not None else {},
            'attributes': list(map(lambda x: x.serialize, self.attributes)), #attributes acording the category
            'sale-price': self.sale_price
        }

    def get_item_stock(self):
        '''returns the global stock of current item
        stock = adquisitions - requisitions
        '''
        adquisitions = db.session.query(func.sum(Adquisition.entry_qtty)).select_from(Item).join(Item.stock).join(Stock.adquisitions).filter(Item.id == self.id).scalar() or 0
        requisitions = db.session.query(Requisition).select_from(Item).join(Item.stock).join(Stock.adquisitions).join(Adquisition.requisitions).filter(Item.id == self.id).count()
                
        return (adquisitions - requisitions)


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
    attributes = db.relationship('Attribute', secondary=attribute_category, back_populates='categories', lazy='dynamic')

    
    def __repr__(self) -> str:
        return f'<Category: {self.name}'

    def serialize(self, basic=False) -> dict:
        rsp = {
            'id': self.id,
            'name': self.name,
        }
        if not basic:
            if self.children != []:
                rsp['sub-categories'] = list(map(lambda x: x.serialize(), self.children))
            else:
                rsp['items']= self.items.count()

        return rsp

    def serialize_path(self) -> dict:
        path = [{"node": "root", "id": 0}]
        p = self.parent
        while p != None:
            path.insert(1, {"node": p.name, "id": p.id})
            p = p.parent
        
        return path

    def check_name_exists(company_id, category_name):
        # return True if _company_id has already an sku with matching value
        q = db.session.query(Category).select_from(User).join(User.company).join(Company.categories).filter(Company.id == company_id, Category.name == func.lower(category_name)).first()

        return True if q is not None else False


class Third(db.Model):
    __tablename__='third'
    id = db.Column(db.Integer, primary_key=True)
    _company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    addresses = db.Column(JSON, default={})
    third_type = db.Column(db.String(64), default="client")
    contacts = db.Column(JSON, default={})
    #relations
    company = db.relationship('Company', back_populates='thirds', lazy='select')
    orders = db.relationship('Order', back_populates='client', lazy='dynamic') #as client only
    adquisitions = db.relationship('Adquisition', back_populates='provider', lazy='dynamic') #as provider only
    items = db.relationship('Item', secondary=item_provider, back_populates='providers', lazy='dynamic')

    def __repr__(self) -> str:
        return f'<Third name: {self.name}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'contacts': self.contacts or []
        }


class Shelf(db.Model):
    __tablename__ = 'shelf'
    id = db.Column(db.Integer, primary_key=True)
    _storage_id = db.Column(db.Integer, db.ForeignKey('storage.id'), nullable=False)
    name = db.Column(db.String(128), default='')
    max_volume = db.Column(db.Float(precision=2), default=99.0)
    max_weight = db.Column(db.Float(precision=2), default=99.0)
    location_ref = db.Column(db.Text)
    one_stock_only = db.Column(db.Boolean, default=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('shelf.id'))
    #relations
    children = db.relationship('Shelf', cascade="all, delete-orphan", backref=backref('parent', remote_side=id))
    storage = db.relationship('Storage', back_populates='shelves', lazy='joined')
    adquisitions = db.relationship('Adquisition', back_populates='shelf', lazy='dynamic')

    def __repr__(self) -> str:
        return f'<Shelf {self.id}'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'name': self.name
        }

    def serialize_data(self) -> dict:
        return {
            'location-ref': self.location_ref,
            'max': {'volume': self.max_volume, 'weight': self.max_weight},
            'one-stock-only': self.one_stock_only
        }

    def serialize_path(self) -> dict:
        path = [{"node": self.storage.name, "id": self.storage.id}]
        p = self.parent
        while p != None:
            path.insert(1, {"name": p.name, "id": p.id})
            p = p.parent
        
        return path


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
    adquisitions = db.relationship('Adquisition', back_populates='stock', lazy='dynamic')

    def __repr__(self) -> str:
        return f'<Item_Entry {self.id}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'item-storage-limits': {'max-stock': self.max, 'min-stock': self.min},
            'method': self.method
        }


class Order(db.Model):
    __tablename__ = 'order'
    id = db.Column(db.Integer, primary_key=True)
    _log = db.Column(JSON)
    _date_created = db.Column(db.DateTime, default=datetime.utcnow)
    _date_closed = db.Column(db.DateTime)
    _client_id = db.Column(db.Integer, db.ForeignKey('third.id'), nullable=False)
    status = db.Column(db.String(128), default='in-review')
    payment_verified = db.Column(db.Boolean, default=False)
    delivery_address = db.Column(JSON)
    delivery_voucher = db.Column(JSON)
    #relations
    requisitions = db.relationship('Requisition', back_populates='order', lazy='dynamic')
    client = db.relationship('Third', back_populates='orders', lazy='select')
    items = db.relationship('ItemInOrder', back_populates='order', lazy='dynamic')


    def __repr__(self) -> str:
        return f'<Order id: {self.id}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'status': self.status,
            'number': f'ORD-{self.id:03d}-{self._date_created.strftime("%d.%m.%Y")}'
        }


class Requisition(db.Model):
    __tablename__ = 'requisition'
    id = db.Column(db.Integer, primary_key=True)
    _log = db.Column(JSON)
    _date_created = db.Column(db.DateTime, default=datetime.utcnow)
    _order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    _adquisition_id = db.Column(db.Integer, db.ForeignKey('adquisition.id'), nullable=False)
    status = db.Column(db.String(32), default='in-review')
    #relations
    order = db.relationship('Order', back_populates='requisitions', lazy='select')
    adquisition = db.relationship('Adquisition', back_populates='requisitions', lazy='select')

    def __repr__(self) -> str:
        return f'<Requisition id: {self.id}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'status': self.status,
            'number': f'REQ-{self.id:03d}-{self._date_created.strftime("%d.%m.%Y")}'
        }


class Adquisition(db.Model):
    __tablename__ = 'adquisition'
    id = db.Column(db.Integer, primary_key=True)
    _entry_date = db.Column(db.DateTime, default=datetime.utcnow)
    _log = db.Column(JSON)
    _stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'), nullable=False)
    entry_qtty = db.Column(db.Float(precision=2), default=0.0)
    unit_cost = db.Column(db.Float(precision=2), default=0.0)
    purchase_ref_num = db.Column(db.String(128))
    provider_part_code = db.Column(db.String(128))
    pkg_weight = db.Column(db.Float(precision=2), default=0.0) #in kg
    pkg_volume = db.Column(db.Float(precision=2), default=0.0) #cm3
    status = db.Column(db.String(32), default='in-review')
    review_img = db.Column(JSON) #imagenes de la revision de los items.
    shelf_id = db.Column(db.Integer, db.ForeignKey('shelf.id'))
    provider_id = db.Column(db.Integer, db.ForeignKey('third.id'))
    #relations
    provider = db.relationship('Third', back_populates='adquisitions', lazy='select')
    stock = db.relationship('Stock', back_populates='adquisitions', lazy='select')
    shelf = db.relationship('Shelf', back_populates='adquisitions', lazy='select')
    requisitions = db.relationship('Requisition', back_populates='adquisition', lazy='dynamic')


    def __repr__(self) -> str:
        return f'<adquisition-id: {self.id}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'status': self.status,
            'number': f'ADQ-{self.id:03d}-{self._entry_date.strftime("%d.%m.%Y")}'
        }


class UnitCatalog(db.Model):
    __tablename__='unit_catalog'
    id = db.Column(db.Integer, primary_key=True)
    _company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    code = db.Column(db.String(32), nullable=False)
    type = db.Column(db.String(64), default='string') #string - number - boolean
    #relations
    company = db.relationship('Company', back_populates='units_catalog', lazy='select')
    attributes = db.relationship('Attribute', back_populates='unit', lazy='dynamic')

    def __repr__(self) -> str:
        return f"<Unit id: {self.id}>"

    def serialize(self) -> dict:
        return {
            'unit-name': self.name,
            'unit-code': self.code,
            'unit-type': self.type
        }


class Attribute(db.Model):
    __tablename__ = 'attribute'
    id = db.Column(db.Integer, primary_key=True)
    _company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    unit_id = db.Column(db.Integer, db.ForeignKey('unit_catalog.id'))
    # relations
    unit = db.relationship('UnitCatalog', back_populates='attributes', lazy='joined')
    company = db.relationship('Company', back_populates='attributes_catalog', lazy='select')
    items = db.relationship('ItemAttribute', back_populates='attribute', lazy='dynamic')
    categories = db.relationship('Category', secondary=attribute_category, back_populates='attributes', lazy='dynamic')

    def __repr__(self) -> str:
        return f'<attribute id: {self.id}>'

    def serialize(self) -> str:
        return {
            'attribute-id': self.id,
            'attribute-name': self.name
        }


class ItemAttribute(db.Model):
    __tablename__ = 'item_attribute'
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.String(64), default="") #unit value for a given attribute
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    attribute_id = db.Column(db.Integer, db.ForeignKey('attribute.id'), nullable=False)
    #relations
    item = db.relationship('Item', back_populates='attributes', lazy='select')
    attribute = db.relationship('Attribute', back_populates='items', lazy='select')

    def __repr__(self) -> str:
        return f'<item-id: {self.item_id} attribute-id: {self.attribute_id}>'

    def serialize(self) -> dict:
        return {
            'unit-value': self.value
        }


class ItemInOrder(db.Model):
    __tablename__ = 'item_in_order'
    id = db.Column(db.Integer, primary_key=True)
    _date_created = db.Column(db.DateTime, default=datetime.utcnow)
    item_qtty = db.Column(db.Float(precision=2), default=0.0)
    unit_price = db.Column(db.Float(precision=2), default=0.0)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    #relations
    item = db.relationship('Item', back_populates='orders', lazy='select')
    order = db.relationship('Order', back_populates='items', lazy='select')

    def __repr__(self) -> str:
        return f"<Item-id:{self.item_id} Order-id:{self.order_id}>"

    def serialize(self) -> dict:
        return {
            "id": self.id,
            "item_qtty": self.item_qtty,
            "unit_price": self.unit_price
        }