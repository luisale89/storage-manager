from app.extensions import db
from datetime import datetime, timedelta

from werkzeug.security import generate_password_hash
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import backref

#models
from .global_models import *
from .assoc_models import (item_category, item_provider)

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(256), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    fname = db.Column(db.String(128))
    lname = db.Column(db.String(128))
    image = db.Column(db.String(256))
    phone = db.Column(db.String(32))
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    email_confirmed = db.Column(db.Boolean)
    status = db.Column(db.String(12))
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
            "image": self.image or "https://server.com/default.png",
            "registration_date": self.registration_date,
            "phone": self.phone or "",
            "user-status": self.status
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
            "email": self.email,
            "phone": self.phone,
            "email-confirmed": self.email_confirmed
        }

    def check_if_user_exists(email) -> bool:
        return True if User.query.filter_by(email = email).first() else False

    @property
    def password(self):
        raise AttributeError('Cannot view password')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password, method='sha256')


class Role(db.Model):
    __tablename__ = 'role'
    id = db.Column(db.Integer, primary_key=True)
    relation_date = db.Column(db.DateTime, default=datetime.utcnow)
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
            'relation-date': self.relation_date,
            '_identifiers': {'user-id': self.user_id, 'company-id': self.company_id, 'role_function-id': self.role_function_id}
        }

class Company(db.Model):
    __tablename__ = 'company'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    code = db.Column(db.String(128), nullable=False)
    address = db.Column(JSON)
    logo = db.Column(db.String(256))
    creation_date = db.Column(db.DateTime, default=datetime.utcnow)
    utc_name = db.Column(db.String(128))
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
            "address": self.address,
            "logo": self.logo or "https://server.com/default.png",
            "creation-date": self.creation_date,
            "plan": self.plan.serialize(),
            "configurations": {
                'currency': self.currency,
                'all-currencies': self.currencies,
                'utc-zone-name': self.utc_name,
            },
            "_identifiers": {'user-id': self.user_id}
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
            'utc': {"latitude": self.latitude or 0.0, "longitude": self.longitude or 0.0},
            '_identifiers': {'company-id': self.company_id}
        }


class Item(db.Model):
    __tablename__='item'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    weight = db.Column(db.Float(precision=2))
    height = db.Column(db.Float(precision=2))
    width = db.Column(db.Float(precision=2))
    depth = db.Column(db.Float(precision=2))
    unit = db.Column(db.String(128))
    sku = db.Column(db.String(128), nullable=False, unique=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    #relations
    company = db.relationship('Company', back_populates='items', lazy='select')
    stock = db.relationship('Stock', back_populates='item', lazy='dynamic')
    categories = db.relationship('Category', secondary=item_category, back_populates='items', lazy='select')
    providers = db.relationship('Provider', secondary=item_provider, back_populates='items', lazy='select')


    def __repr__(self) -> str:
        return f'<Item: {self.name}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'package-weight': self.weight,
            'package-dimensions': {'height': self.height, 'width': self.width, 'depth': self.depth},
            'sku': self.sku,
            'unit': self.unit,
            'categories': list(map(lambda x:x.serialize(), self.categories)),
            '_identifiers': {'company-id': self.company_id}
        }

    def check_if_sku_exists(sku_code) -> bool:
        return True if Item.query.filter_by(sku=sku_code).first() else False

    def get_item_stock(self):
        query = Item.query.filter(Item.id == self.id).join(Item.stock)

        entries = sum(list(map(lambda x: x.qtty, query.join(Stock.stock_entries).all())))
        requisitions = sum(list(map(lambda x: x.qtty, query.join(Stock.requisitions).all())))
        return entries - requisitions


class Category(db.Model):
    __tablename__= 'category'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    #relations
    company = db.relationship('Company', back_populates='categories', lazy='select')
    items = db.relationship('Item', secondary=item_category, back_populates='categories', lazy='select')
    
    def __repr__(self) -> str:
        return f'<Category: {self.name}'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'name': self.name
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
            'contacts': self.contacts or [],
            '_identifiers': {'company-id': self.company_id}
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
    requisitions = db.relationship('Requisition', back_populates='client', lazy='select')

    def __repr__(self) -> str:
        return f'<Client name: {self.fname}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'contacts': self.contacts or [],
            '_identifiers': self.company_id
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
            '_identifiers': {'storage-id': self.storage_id, 'parent-shelf': self.parent_id}
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
            'method': self.method,
            '_identifiers': {'item-id': self.item_id, 'storage-id': self.storage_id}
        }


class Requisition(db.Model):
    __tablename__ = 'requisition'
    id = db.Column(db.Integer, primary_key=True)
    date_created  = db.Column(db.DateTime, default = datetime.utcnow)
    stock_qtty = db.Column(db.Float(precision=2), default=1)
    status = db.Column(db.String(32))
    delivery_address = db.Column(JSON)
    client_id = db.Column(db.Integer, db.ForeignKey('client.id'))
    stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'), nullable=False)
    log = db.Column(JSON)
    #relations
    client = db.relationship('Client', back_populates='requisitions', lazy='select')
    stock = db.relationship('Stock', back_populates='requisitions', lazy='select')
    dispatches = db.relationship('Dispatch', back_populates='requisition', lazy='dynamic')

    def __repr__(self) -> str:
        return f'<Requisition id: {self.id}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'date-created': self.date_created,
            'stock-qtty-required': self.stock_qtty,
            'status': self.status,
            'delivery-address': self.delivery_address,
            '_identifiers': {'client-id': self.client_id, 'stock-id': self.stock_id}
        }


class StockEntry(db.Model):
    __tablename__ = 'stock_entry'
    id = db.Column(db.Integer, primary_key=True)
    entry_qtty = db.Column(db.Float(precision=2), default=1)
    unit_cost = db.Column(db.Float(precision=2), default=0)
    entry_date = db.Column(db.DateTime, default=datetime.utcnow)
    purchase_ref_num = db.Column(db.String(128))
    qr_code = db.Column(db.String(128))
    review_img = db.Column(JSON) #imagenes de la revision de los items.
    log = db.Column(JSON)
    provider_id = db.Column(db.Integer, db.ForeignKey('provider.id'))
    stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'), nullable=False)
    #relations
    provider = db.relationship('Provider', back_populates='stock_entries', lazy='select')
    stock = db.relationship('Stock', back_populates='stock_entries', lazy='select')
    inventories = db.relationship('Inventory', back_populates='stock_entry', lazy='select')

    def __repr__(self) -> str:
        return f'<stock_entry id: {self.id}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'entry-qtty': self.entry_qtty,
            'unit-cost': self.unit_cost,
            'entry-date': self.entry_date,
            'qr-code': self.qr_code,
            'purchase-reference': self.purchase_ref_num,
            'review-images': self.review_img,
            '_idenfifiers': {'provider-id': self.provider_id, 'stock-id': self.stock_id}     
        }


class Inventory(db.Model):
    __tablename__='inventory'
    id = db.Column(db.Integer, primary_key=True)
    income_date = db.Column(db.DateTime, default = datetime.utcnow)
    last_review = db.Column(db.DateTime)
    stock_entry_id = db.Column(db.Integer, db.ForeignKey('stock_entry.id'), nullable=False)
    shelf_id = db.Column(db.Integer, db.ForeignKey('shelf.id'), nullable=False)
    log = db.Column(JSON)
    #relations
    stock_entry = db.relationship('StockEntry', back_populates='inventories', lazy='select')
    shelf = db.relationship('Shelf', back_populates='inventories', lazy='select')
    dispatches = db.relationship('Dispatch', back_populates='inventory', lazy='dynamic')

    def __repr__(self) -> str:
        return f'<Inventory id: {self.id}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'income_date': self.income_date,
            'last_review': self.last_review,
            '_identifiers': {'entry-id': self.stock_entry_id, 'shelf-id': self.shelf_id}
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
            'review-img': self.review_img,
            '_identifiers': {'requisition-id': self.requisition_id, 'inventory-id': self.inventory_id}
        }