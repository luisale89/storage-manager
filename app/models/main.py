from app.extensions import db
from datetime import datetime

from werkzeug.security import generate_password_hash
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import backref
from sqlalchemy import func

from app.utils.helpers import datetime_formatter, DefaultImages

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
    image = db.Column(db.String(256), default=DefaultImages().user)
    phone = db.Column(db.String(32), default="")
    #relations
    roles = db.relationship('Role', back_populates='user', lazy='joined')
    company = db.relationship('Company', back_populates='user', uselist=False, lazy='joined')

    def __repr__(self):
        # return '<User %r>' % self.id
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
    code = db.Column(db.String(128), nullable=False)
    address = db.Column(JSON, default={})
    logo = db.Column(db.String(256), default=DefaultImages().company)
    currency = db.Column(db.Integer, default = 0)
    currencies = db.Column(JSON, default={"all": [{"name": "US Dollar", "code": "USD", "rate-usd": 1.0}]})
    tz_name = db.Column(db.String(128), default="america/caracas")
    #relationships
    user = db.relationship('User', back_populates='company', lazy='select')
    plan = db.relationship('Plan', back_populates='companies', lazy='joined')
    roles = db.relationship('Role', back_populates='company', lazy='dynamic')
    storages = db.relationship('Storage', back_populates='company', lazy='dynamic')
    items = db.relationship('Item', back_populates='company', lazy='dynamic')
    categories = db.relationship('Category', back_populates='company', lazy='dynamic')
    thirds = db.relationship('Third', back_populates='company', lazy='dynamic')
    unit_catalog = db.relationship('UnitCatalog', back_populates='company', lazy='dynamic')
    attribute_catalog = db.relationship('AttributeCatalog', back_populates='company', lazy='dynamic')

    def __repr__(self) -> str:
        # return '<Company %r>' % self.id
        return f"<Company {self.id}>"

    def serialize(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "address": self.address,
            "logo": self.logo,
            "currency": self.currencies.get('all', {"name": "US Dollar", "code": "USD", "rate-usd": 1.0})[0],
            "time-zone-name": self.tz_name,
            "plan": self.plan.name,
        }


class Storage(db.Model):
    __tablename__ = 'storage'
    id = db.Column(db.Integer, primary_key=True)
    _company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(128), nullable=True)
    description = db.Column(db.Text)
    code = db.Column(db.String(64))
    address = db.Column(JSON, default={})
    latitude = db.Column(db.Float(precision=6))
    longitude = db.Column(db.Float(precision=6))
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
            'code': self.code or "",
            'address': self.address,
            'utc': {
                "latitude": self.latitude or 0.0, 
                "longitude": self.longitude or 0.0
            }
        }

    def check_code_exists(company_id, code):
        # return True if _company_id has already an sku with matching value
        q = db.session.query(Storage).select_from(User).join(User.company).join(Company.storages).filter(Company.id == company_id, Storage.code == func.lower(code)).first()
        
        return True if q is not None else False


class Item(db.Model):
    __tablename__='item'
    id = db.Column(db.Integer, primary_key=True)
    _company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    sku = db.Column(db.String(128))
    description = db.Column(db.Text)
    weight = db.Column(db.Float(precision=2), default=0.0)
    height = db.Column(db.Float(precision=2), default=0.0)
    width = db.Column(db.Float(precision=2), default=0.0)
    depth = db.Column(db.Float(precision=2), default=0.0)
    unit = db.Column(db.String(128))
    images = db.Column(JSON, default={'urls': [DefaultImages().item]})
    documents = db.Column(JSON)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    #relations
    company = db.relationship('Company', back_populates='items', lazy='select')
    stock = db.relationship('Stock', back_populates='item', lazy='dynamic')
    category = db.relationship('Category', back_populates='items', lazy='joined')
    providers = db.relationship('Third', secondary=item_provider, back_populates='items', lazy='dynamic')
    attributes = db.relationship('Attribute', back_populates='item', lazy='dynamic')


    def __repr__(self) -> str:
        return f'<Item: {self.name}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'sku': self.sku
        }

    def serialize_fav_image(self) -> dict:
        return {
            'image': self.images.get('urls', [DefaultImages().item])[0] #return first image in json object
        }

    def serialize_datasheet(self) -> dict:
        return {
            'unit': self.unit,
            'package': {
                'weight': self.weight,
                'dimensions': {'height': self.height, 'width': self.width, 'depth': self.depth}
            },
            'images': self.images.get('urls', [DefaultImages().item]), #return all images in json object
            'documents': self.documents.get('urls', []),
            'category': self.category.serialize() if self.category is not None else {},
            'attributes': list(map(lambda x: x.serialize, self.attributes))
        }

    def check_sku_exists(company_id, sku):
        # return True if _company_id has already an sku with matching value
        q = db.session.query(Item).select_from(User).join(User.company).join(Company.items).filter(Company.id == company_id, Item.sku == func.lower(sku)).first()
        
        return True if q is not None else False

    def get_item_stock(self):
        '''returns the global stock of current item
        stock = adquisitions - requisitions
        '''
        adquisitions = db.session.query(func.sum(Adquisition.entry_qtty)).select_from(Item).join(Item.stock).join(Stock.adquisitions).filter(Item.id == self.id).scalar() or 0
        requisitions = db.session.query(func.sum(Requisition.required_qtty)).select_from(Item).join(Item.stock).join(Stock.adquisitions).join(Adquisition.requisitions).filter(Item.id == self.id).scalar() or 0
                
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
    attributes = db.relationship('AttributeCatalog', secondary=attribute_category, back_populates='categories', lazy='dynamic')

    
    def __repr__(self) -> str:
        return f'<Category: {self.name}'

    def serialize(self) -> dict:

        rsp = {
            'id': self.id,
            'name': self.name,
        }
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
    third_type = db.Column(db.String(64), default="client")
    name = db.Column(db.String(128), nullable=False)
    code = db.Column(db.String(128))
    contacts = db.Column(JSON, default={})
    #relations
    company = db.relationship('Company', back_populates='thirds', lazy='select')
    orders = db.relationship('Order', back_populates='client', lazy='dynamic')
    adquisitions = db.relationship('Adquisition', back_populates='provider', lazy='dynamic')
    items = db.relationship('Item', secondary=item_provider, back_populates='providers', lazy='dynamic')

    def __repr__(self) -> str:
        return f'<Third name: {self.name}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'contacts': self.contacts or []
        }


class Shelf(db.Model):
    __tablename__ = 'shelf'
    id = db.Column(db.Integer, primary_key=True)
    _storage_id = db.Column(db.Integer, db.ForeignKey('storage.id'), nullable=False)
    code = db.Column(db.String(128), nullable=False)
    max_volume = db.Column(db.Float(precision=2))
    max_weight = db.Column(db.Float(precision=2))
    loc_reference = db.Column(db.Text)
    loc_column = db.Column(db.Integer)
    loc_row = db.Column(db.Integer)
    one_stock_only = db.Column(db.Boolean, default=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('shelf.id'))
    adquisition_id = db.Column(db.Integer, db.ForeignKey('adquisition.id'))
    #relations
    children = db.relationship('Shelf', cascade="all, delete-orphan", backref=backref('parent', remote_side=id))
    storage = db.relationship('Storage', back_populates='shelves', lazy='joined')
    adquisition = db.relationship('Adquisition', back_populates='shelves', lazy='select')

    def __repr__(self) -> str:
        return f'<Shelf {self.code}'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'code': self.code
        }

    def serialize_data(self) -> dict:
        return {
            'location': {'reference': self.loc_reference, 'matrix': {'column': self.loc_column, 'row': self.loc_row}},
            'max': {'volume': self.max_volume, 'weight': self.max_weight},
            'one-stock-only': self.one_stock_only
        }

    def serialize_path(self) -> dict:
        path = [{"node": "root", "id": 0}]
        p = self.parent
        while p != None:
            path.insert(1, {"node": p.code, "id": p.id})
            p = p.parent
        
        return path


class Stock(db.Model):
    __tablename__ = 'stock'
    id = db.Column(db.Integer, primary_key=True)
    _storage_id = db.Column(db.Integer, db.ForeignKey('storage.id'), nullable=False)
    _item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    max = db.Column(db.Float(precision=2))
    min = db.Column(db.Float(precision=2))
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
    code = db.Column(db.String(128), nullable=False)
    state = db.Column(db.String(128))
    delivery_address = db.Column(JSON)
    delivery_voucher = db.Column(JSON)
    #relations
    requisitions = db.relationship('Requisition', back_populates='order', lazy='dynamic')
    client = db.relationship('Third', back_populates='orders', lazy='select')


    def __repr__(self) -> str:
        return f'<Order id: {self.id}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'date-created': datetime_formatter(self._date_created),
            'code': self.code,
            'status': {
                'state': self.state,
                'date-closed': datetime_formatter(self._date_closed),
            },
            'delivery-address': self.delivery_address,
            'delivery-voucher': self.delivery_voucher
        }


class Requisition(db.Model):
    __tablename__ = 'requisition'
    id = db.Column(db.Integer, primary_key=True)
    _log = db.Column(JSON)
    _date_created = db.Column(db.DateTime, default=datetime.utcnow)
    _order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    _adquisition_id = db.Column(db.Integer, db.ForeignKey('adquisition.id'), nullable=False)
    required_qtty = db.Column(db.Float(precision=2), default=0.0)
    status = db.Column(db.String(32))
    #relations
    order = db.relationship('Order', back_populates='requisitions', lazy='select')
    adquisition = db.relationship('Adquisition', back_populates='requisitions', lazy='select')

    def __repr__(self) -> str:
        return f'<Requisition id: {self.id}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'stock-qtty-required': self.required_qtty,
            'status': self.status,
            'date-created': datetime_formatter(self._date_created)
        }


class Adquisition(db.Model):
    __tablename__ = 'adquisition'
    id = db.Column(db.Integer, primary_key=True)
    _qr_code = db.Column(db.String(128))
    _entry_date = db.Column(db.DateTime, default=datetime.utcnow)
    _log = db.Column(JSON)
    _stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'), nullable=False)
    entry_qtty = db.Column(db.Float(precision=2), default=0.0)
    unit_cost = db.Column(db.Float(precision=2), default=0.0)
    purchase_ref_num = db.Column(db.String(128))
    provider_part_code = db.Column(db.String(128))
    review_img = db.Column(JSON) #imagenes de la revision de los items.
    provider_id = db.Column(db.Integer, db.ForeignKey('third.id'))
    #relations
    provider = db.relationship('Third', back_populates='adquisitions', lazy='select')
    stock = db.relationship('Stock', back_populates='adquisitions', lazy='select')
    shelves = db.relationship('Shelf', back_populates='adquisition', lazy='dynamic')
    requisitions = db.relationship('Requisition', back_populates='adquisition', lazy='dynamic')


    def __repr__(self) -> str:
        return f'<adquisition-id: {self.id}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'entry-qtty': self.entry_qtty,
            'unit-cost': self.unit_cost,
            'entry-date': datetime_formatter(self._entry_date),
            'qr-code': self._qr_code,
            'purchase-code': self.purchase_ref_num,
            'provider-part-code': self.provider_part_code,
            'review-images': self.review_img,
        }


class UnitCatalog(db.Model):
    __tablename__='unit_catalog'
    id = db.Column(db.Integer, primary_key=True)
    _company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    type = db.Column(db.String(128), default = "unit")
    #relations
    company = db.relationship('Company', back_populates='unit_catalog', lazy='select')
    attributes = db.relationship('Attribute', back_populates='unit_catalog', lazy='dynamic')

    def __repr__(self) -> str:
        return f"<Unit id: {self.id}>"

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type
        }


class AttributeCatalog(db.Model):
    __tablename__ = 'attribute_catalog'
    id = db.Column(db.Integer, primary_key=True)
    _company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    code = db.Column(db.String(128), nullable=False)
    field_type = db.Column(db.String(64), default="text")
    # relations
    company = db.relationship('Company', back_populates='attribute_catalog', lazy='select')
    attributes = db.relationship('Attribute', back_populates='attribute_catalog', lazy='dynamic')
    categories = db.relationship('Category', secondary=attribute_category, back_populates='attributes', lazy='dynamic')

    def __repr__(self) -> str:
        return f'<attribute id: {self.id}>'

    def serialize(self) -> str:
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'form-field-type': self.field_type
        }


class Attribute(db.Model):
    __tablename__ = 'attribute'
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.String(128), default="")
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    att_catalog_id = db.Column(db.Integer, db.ForeignKey('attribute_catalog.id'), nullable=False)
    unit_catalog_id = db.Column(db.Integer, db.ForeignKey('unit_catalog.id'), nullable=False)
    #relations
    item = db.relationship('Item', back_populates='attributes', lazy='select')
    attribute_catalog = db.relationship('AttributeCatalog', back_populates='attributes', lazy='joined')
    unit_catalog = db.relationship('UnitCatalog', back_populates='attributes', lazy='joined')

    def __repr__(self) -> str:
        return f'<attribute id: {self.id}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'value': self.value,
        }