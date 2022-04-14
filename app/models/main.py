from app.extensions import db
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import backref
from sqlalchemy import func

#models
from .global_models import *
from .assoc_models import item_provider

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    _email = db.Column(db.String(256), unique=True, nullable=False)
    _password_hash = db.Column(db.String(256), nullable=False)
    _registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    _email_confirmed = db.Column(db.Boolean)
    _status = db.Column(db.String(12))
    fname = db.Column(db.String(128))
    lname = db.Column(db.String(128))
    image = db.Column(db.String(256))
    phone = db.Column(db.String(32))
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
            "image": self.image or "https://server.com/default.png"
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
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'))
    role_function_id = db.Column(db.Integer, db.ForeignKey('role_function.id'), nullable=False)
    #relations
    user = db.relationship('User', back_populates='roles', lazy='joined')
    company = db.relationship('Company', back_populates='roles', lazy='joined')
    role_function = db.relationship('RoleFunction', back_populates='roles', lazy='joined')

    def __repr__(self) -> str:
        return f'<User {self.user_id} - Company {self.company_id} - Role {self.company_id}'

    def serialize(self) -> dict:
        return {
            'role-id': self.id,
            'relation-date': self._relation_date
        }

class Company(db.Model):
    __tablename__ = 'company'
    id = db.Column(db.Integer, primary_key=True)
    _creation_date = db.Column(db.DateTime, default=datetime.utcnow)
    name = db.Column(db.String(128), nullable=False)
    code = db.Column(db.String(128), nullable=False)
    address = db.Column(JSON)
    logo = db.Column(db.String(256))
    currency = db.Column(JSON, default = {'name': 'US Dollar', 'code': 'USD', 'rate-USD': 1.0,})
    currencies = db.Column(JSON)
    plan_id = db.Column(db.Integer, db.ForeignKey('plan.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    #relationships
    user = db.relationship('User', back_populates='company', lazy='select')
    plan = db.relationship('Plan', back_populates='companies', lazy='joined')
    roles = db.relationship('Role', back_populates='company', lazy='dynamic')
    storages = db.relationship('Storage', back_populates='company', lazy='dynamic')
    items = db.relationship('Item', back_populates='company', lazy='dynamic')
    categories = db.relationship('Category', back_populates='company', lazy='dynamic')
    providers = db.relationship('Provider', back_populates='company', lazy='dynamic')
    clients = db.relationship('Client', back_populates='company', lazy='dynamic')

    def __repr__(self) -> str:
        # return '<Company %r>' % self.id
        return f"<Company {self.id}>"

    def serialize(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "code": self.code,
            "logo": self.logo or "https://server.com/default.png",
            "plan": {'name': self.plan.name, 'id': self.plan_id},
        }


class Storage(db.Model):
    __tablename__ = 'storage'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=True)
    description = db.Column(db.Text)
    code = db.Column(db.String(64))
    address = db.Column(JSON)
    latitude = db.Column(db.Float(precision=6))
    longitude = db.Column(db.Float(precision=6))
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
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
            'address': self.address or "",
            'utc': {
                "latitude": self.latitude or 0.0, 
                "longitude": self.longitude or 0.0
            }
        }


class Item(db.Model):
    __tablename__='item'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    sku = db.Column(db.String(128), nullable=False, unique=True)
    description = db.Column(db.Text)
    weight = db.Column(db.Float(precision=2))
    height = db.Column(db.Float(precision=2))
    width = db.Column(db.Float(precision=2))
    depth = db.Column(db.Float(precision=2))
    unit = db.Column(db.String(128))
    attributes = db.Column(JSON)
    images = db.Column(JSON)
    documents = db.Column(JSON)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    #relations
    company = db.relationship('Company', back_populates='items', lazy='select')
    stock = db.relationship('Stock', back_populates='item', lazy='dynamic')
    category = db.relationship('Category', back_populates='items', lazy='joined')
    providers = db.relationship('Provider', secondary=item_provider, back_populates='items', lazy='select')


    def __repr__(self) -> str:
        return f'<Item: {self.name}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'sku': self.sku,
            'images': self.images or []
        }

    def serialize_datasheet(self) -> dict:
        return {
            'unit': self.unit,
            'attributes': self.attributes or [], 
            'documents': self.documents or [],
            'package': {
                'weight': self.weight,
                'dimensions': {'height': self.height, 'width': self.width, 'depth': self.depth}
            }
        }

    def check_if_sku_exists(sku_code) -> bool:
        return True if Item.query.filter_by(sku=sku_code).first() else False

    def get_item_stock(self):
        '''returns the global stock of current item
        stock = stock_entries - stock_requisitions
        '''
        entries = db.session.query(func.sum(StockEntry.entry_qtty)).select_from(Item).join(Item.stock).join(Stock.stock_entries).filter(Item.id == self.id).scalar() or 0
        requisitions = db.session.query(func.sum(Requisition.stock_qtty)).select_from(Item).join(Item.stock).join(Stock.requisitions).filter(Item.id == self.id).scalar() or 0
                
        return (entries - requisitions)


class Category(db.Model):
    __tablename__= 'category'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    attribute_form = db.Column(JSON)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    #relations
    children = db.relationship('Category', cascade="all, delete-orphan", backref=backref('parent', remote_side=id))
    company = db.relationship('Company', back_populates='categories', lazy='select')
    items = db.relationship('Item', back_populates='category', lazy='dynamic')

    
    def __repr__(self) -> str:
        return f'<Category: {self.name}'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'name': self.name
        }

    def serialize_path(self) -> dict: #path to root
        return {
            'name': self.name,
            'id': self.id,
            'parent': self.parent.serialize_path() if self.parent is not None else 'home'
        }


class Provider(db.Model):
    __tablename__ = 'provider'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    provider_code = db.Column(db.String(128), nullable=False)
    contacts = db.Column(JSON)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    #relations
    company = db.relationship('Company', back_populates='providers', lazy='select')
    items = db.relationship('Item', secondary=item_provider, back_populates='providers', lazy='select')
    stock_entries = db.relationship('StockEntry', back_populates='provider', lazy='dynamic')

    def __repr__(self) -> str:
        return f'<Provider: {self.name}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'code': self.provider_code,
            'contacts': self.contacts or []
        }


class Client(db.Model):
    __tablename__='client'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    code = db.Column(db.String(128))
    contacts = db.Column(JSON)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    #relations
    company = db.relationship('Company', back_populates='clients', lazy='select')
    orders = db.relationship('Order', back_populates='client', lazy='dynamic')

    def __repr__(self) -> str:
        return f'<Client name: {self.fname}>'

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
    code = db.Column(db.String(128), nullable=False)
    max_volume = db.Column(db.Float(precision=2))
    max_weight = db.Column(db.Float(precision=2))
    loc_reference = db.Column(db.Text)
    loc_column = db.Column(db.Integer)
    loc_row = db.Column(db.Integer)
    one_stock_only = db.Column(db.Boolean, default=False)
    storage_id = db.Column(db.Integer, db.ForeignKey('storage.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('shelf.id'))
    #relations
    children = db.relationship('Shelf', cascade="all, delete-orphan", backref=backref('parent', remote_side=id))
    storage = db.relationship('Storage', back_populates='shelves', lazy='joined')
    inventories = db.relationship('Inventory', back_populates='shelf', lazy='dynamic')

    def __repr__(self) -> str:
        return f'<Shelf {self.code}'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'code': self.code,
            'location': {'reference': self.loc_reference, 'matrix': {'column': self.loc_column, 'row': self.loc_row}},
            'max': {'volume': self.max_volume, 'weight': self.max_weight},
            'one-stock-only': self.one_stock_only
        }

    def serialize_path(self) -> dict: #path to root
        return {
            ** self.serialize(),
            'parent': self.parent.serialize_path() if self.parent is not None else 'root'
        }


class Stock(db.Model):
    __tablename__ = 'stock'
    id = db.Column(db.Integer, primary_key=True)
    max = db.Column(db.Float(precision=2))
    min = db.Column(db.Float(precision=2))
    method = db.Column(db.String(64), default='FIFO')
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    storage_id = db.Column(db.Integer, db.ForeignKey('storage.id'), nullable=False)
    #relations
    item = db.relationship('Item', back_populates='stock', lazy='select')
    storage = db.relationship('Storage', back_populates='stock', lazy='select')
    requisitions = db.relationship('Requisition', back_populates='stock', lazy='dynamic')
    stock_entries = db.relationship('StockEntry', back_populates='stock', lazy='dynamic')

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
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    code = db.Column(db.String(128), nullable=False)
    date_closed = db.Column(db.DateTime)
    state = db.Column(db.String(128))
    delivery_address = db.Column(JSON)
    delivery_voucher = db.Column(JSON)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'), nullable=False)
    log = db.Column(JSON)
    #relations
    requisitions = db.relationship('Requisition', back_populates='order', lazy='joined')
    client = db.relationship('Client', back_populates='orders', lazy='select')


    def __repr__(self) -> str:
        return f'<Order id: {self.id}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'date-created': self.date_created,
            'code': self.code,
            'status': {
                'state': self.state,
                'date-closed': self. date_closed,
            },
            'delivery-address': self.delivery_address,
            'delivery-voucher': self.delivery_voucher
        }


class Requisition(db.Model):
    __tablename__ = 'requisition'
    id = db.Column(db.Integer, primary_key=True)
    stock_qtty = db.Column(db.Float(precision=2), default=1)
    status = db.Column(db.String(32))
    stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    log = db.Column(JSON)
    #relations
    stock = db.relationship('Stock', back_populates='requisitions', lazy='select')
    order = db.relationship('Order', back_populates='requisitions', lazy='select')
    dispatches = db.relationship('Dispatch', back_populates='requisition', lazy='dynamic')

    def __repr__(self) -> str:
        return f'<Requisition id: {self.id}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'stock-qtty-required': self.stock_qtty,
            'status': self.status
        }


class StockEntry(db.Model):
    __tablename__ = 'stock_entry'
    id = db.Column(db.Integer, primary_key=True)
    _qr_code = db.Column(db.String(128))
    _entry_date = db.Column(db.DateTime, default=datetime.utcnow)
    entry_qtty = db.Column(db.Float(precision=2), default=1)
    unit_cost = db.Column(db.Float(precision=2), default=0)
    purchase_ref_num = db.Column(db.String(128))
    provider_part_code = db.Column(db.String(128))
    review_img = db.Column(JSON) #imagenes de la revision de los items.
    log = db.Column(JSON)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.id'))
    provider_id = db.Column(db.Integer, db.ForeignKey('provider.id'))
    stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'), nullable=False)
    #relations
    provider = db.relationship('Provider', back_populates='stock_entries', lazy='select')
    stock = db.relationship('Stock', back_populates='stock_entries', lazy='select')
    inventory = db.relationship('Inventory', back_populates='stock_entries', lazy='select')

    def __repr__(self) -> str:
        return f'<stock_entry id: {self.id}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'entry-qtty': self.entry_qtty,
            'unit-cost': self.unit_cost,
            'entry-date': self._entry_date,
            'qr-code': self._qr_code,
            'purchase-code': self.purchase_ref_num,
            'provider-part-code': self.provider_part_code,
            'review-images': self.review_img,
        }


class Inventory(db.Model):
    __tablename__='inventory'
    id = db.Column(db.Integer, primary_key=True)
    _income_date = db.Column(db.DateTime, default = datetime.utcnow)
    last_review = db.Column(db.DateTime)
    log = db.Column(JSON)
    shelf_id = db.Column(db.Integer, db.ForeignKey('shelf.id'), nullable=False)
    #relations
    stock_entries = db.relationship('StockEntry', back_populates='inventory', lazy='dynamic')
    shelf = db.relationship('Shelf', back_populates='inventories', lazy='select')
    dispatches = db.relationship('Dispatch', back_populates='inventory', lazy='dynamic')

    def __repr__(self) -> str:
        return f'<Inventory id: {self.id}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'income_date': self._income_date,
            'last_review': self.last_review
        }


class Dispatch(db.Model):
    __tablename__='dispatch'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default= datetime.utcnow)
    status = db.Column(db.String(128), default='in_review')
    review_img = db.Column(JSON)
    requisition_id = db.Column(db.Integer, db.ForeignKey('requisition.id'), nullable=False)
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.id'), nullable=False)
    #relations
    requisition = db.relationship('Requisition', back_populates='dispatches', lazy='select')
    inventory = db.relationship('Inventory', back_populates='dispatches', lazy='select')

    def __repr__(self) -> str:
        return f'<dispatch id: {self.id}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'date': self.date,
            'status': self.status,
            'review-img': self.review_img
        }