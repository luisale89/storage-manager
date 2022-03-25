from app.extensions import db
from datetime import datetime

from werkzeug.security import generate_password_hash
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import backref

#models
from .global_models import *
from .purchase_models import *
from .assoc_models import (item_category, item_provider, sale_stock)

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(256), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    fname = db.Column(db.String(128))
    lname = db.Column(db.String(128))
    image = db.Column(db.String(256))
    home_address = db.Column(JSON)
    phone = db.Column(db.String(32))
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    email_confirmed = db.Column(db.Boolean)
    status = db.Column(db.String(12))
    #relations
    companies = db.relationship('UserCompany', back_populates='user', lazy='select')

    def __repr__(self):
        # return '<User %r>' % self.id
        return f"<User {self.id}>"

    def serialize(self) -> dict:
        return {
            "id": self.id,
            "fname" : self.fname,
            "lname" : self.lname,
            "image": self.image if self.image is not None else "https://server.com/default.png",
            "registration_date": self.registration_date,
            "home_address": self.home_address,
            "phone": self.phone,
            "user_status": self.status
        }

    def serialize_private(self) -> dict:
        return {
            "email": self.email,
            "home_address": self.home_address,
            "phone": self.phone,
            "email_confirmed": self.email_confirmed
        }

    def check_if_user_exists(email) -> bool:
        return True if User.query.filter_by(email = email).first() else False


    @property
    def password(self):
        raise AttributeError('Cannot view password')

    @password.setter
    def password(self, password):
        self.password_hash = generate_password_hash(password, method='sha256')


class UserCompany(db.Model):
    __tablename__ = 'user_company'
    id = db.Column(db.Integer, primary_key=True)
    relation_date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('role.id'), nullable=False)
    #relations
    user = db.relationship('User', back_populates='companies', lazy='select')
    company = db.relationship('Company', back_populates='users', lazy='select')
    role = db.relationship('Role', back_populates='user_company', lazy='select')

    def __repr__(self) -> str:
        return f'<User {self.user_id} - Company {self.company_id} - Role {self.company_id}'

    def serialize(self) -> dict:
        return {
            'role': self.role.serialize(),
            'relation_date': self.relation_date
        }


class Company(db.Model):
    __tablename__ = 'company'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    company_code = db.Column(db.String(128), nullable=False, unique=True)
    image = db.Column(db.String(256))
    main_email = db.Column(db.String(256), nullable=False)
    address = db.Column(JSON)
    contacts = db.Column(JSON)
    latitude = db.Column(db.Float(precision=8))
    longitude = db.Column(db.Float(precision=8))
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    plan_id = db.Column(db.Integer, db.ForeignKey('plan.id'), nullable=False)
    #relationships
    plan = db.relationship('Plan', back_populates='companies', lazy='joined')
    users = db.relationship('UserCompany', back_populates='company', lazy='select')
    storages = db.relationship('Storage', back_populates='company', lazy='select')
    items = db.relationship('Item', back_populates='company', lazy='select')
    categories = db.relationship('Category', back_populates='company', lazy='joined')
    providers = db.relationship('Provider', back_populates='company', lazy='select')

    def __repr__(self) -> str:
        # return '<Company %r>' % self.id
        return f"<Company {self.id}>"

    def serialize(self) -> dict:
        return {
            "name": self.name,
            "company_code": self.company_code,
            "image": self.image if self.image is not None else "https://server.com/default.png",
            "address": self.address,
            "contacts": self.contacts,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "registration_date": self.registration_date
        }

    def check_if_company_exists(company_q_code) -> bool:
        return True if Company.query.filter_by(company_code = company_q_code).first() else False


class Storage(db.Model):
    __tablename__ = 'storage'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=True)
    description = db.Column(db.Text)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    #relations
    company = db.relationship('Company', back_populates='storages', lazy='select')
    locations = db.relationship('Location', back_populates='storage', lazy='select')

    def __repr__(self) -> str:
        return f'<Storage {self.name}>'

    def serialize(self):
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description
        }


class Location(db.Model):
    __tablename__ = 'location'
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(128), nullable=False)
    priority = db.Column(db.Integer)
    is_rack = db.Column(db.Boolean)
    storage_id = db.Column(db.Integer, db.ForeignKey('storage.id'), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('location.id'))
    #relations
    storage = db.relationship('Storage', back_populates='locations', lazy='select')
    children = db.relationship('Location', cascade="all, delete-orphan", backref=backref('parent', remote_side=id))
    items = db.relationship('Stock', back_populates='location', lazy='select')

    def __repr__(self) -> str:
        return f'<Location {self.code}'

    def serialize(self) -> dict:
        return {
            'code': self.code,
            'priority': self.priority,
            'is_rack': self.is_rack
        }

    def serialize_path(self) -> dict: #path to root
        return {
            ** self.serialize(),
            'parent': self.parent.serialize_path() if self.parent is not None else 'root'
        }


class Item(db.Model):
    __tablename__='item'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    description = db.Column(db.Text)
    sku = db.Column(db.String(128), nullable=False, unique=True)
    unit = db.Column(db.String(128))
    cost_config = db.Column(db.String(64))
    _util = db.Column(db.Float(precision=2))
    sale_price = db.Column(db.Float(precision=2))
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    #relations
    company = db.relationship('Company', back_populates='items', lazy='select')
    locations = db.relationship('Stock', back_populates='item', lazy='select')
    categories = db.relationship('Category', secondary=item_category, back_populates='items', lazy='joined')
    providers = db.relationship('Provider', secondary=item_provider, back_populates='items', lazy='select')

    def __repr__(self) -> str:
        return f'<Item: {self.name}>'

    def serialize(self) -> dict:
        return {
            'name': self.name,
            'description': self.description,
            'sku': self.sku,
            'unit': self.unit,
            'price_config': self.price_config
        }

    def check_if_sku_exists(sku_code) -> bool:
        return True if Item.query.filter_by(sku=sku_code).first() else False


class Category(db.Model):
    __tablename__= 'category'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    #relations
    company = db.relationship('Company', back_populates='categories', lazy='select')
    items = db.relationship('Iten', secondary=item_category, back_populates='categories', lazy='joined')
    
    def __repr__(self) -> str:
        return f'<Category: {self.name}'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code
        }


class Provider(db.Model):
    __tablename__ = 'provider'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    provider_code = db.Column(db.String(128), nullable=False, unique=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    #relations
    company = db.relationship('Company', back_populates='providers', lazy='select')
    items = db.relationship('Item', secondary=item_provider, back_populates='providers', lazy='joined')

    def __repr__(self) -> str:
        return f'<Provider: {self.name}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'code': self.provider_code
        }

    def check_if_provider_exists(q_code):
        return True if Provider.query.filter_by(provider_code = q_code).first() else False


class Client(db.Model):
    __tablename__='client'
    id = db.Column(db.Integer, primary_key=True)
    fname = db.Column(db.String(128), nullable=False)
    lname = db.Column(db.String(128))
    #relations

    def __repr__(self) -> str:
        return f'<Client name: {self.fname}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'fname': self.fname,
            'lname': self.lname
        }


class Stock(db.Model):
    __tablename__ = 'stock'
    id = db.Column(db.Integer, primary_key=True)
    input_date = db.Column(db.DateTime, default=datetime.utcnow)
    item_cost = db.Column(db.Float(precision=2))
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    location_id = db.Column(db.Integer, db.ForeignKey('location.id'), nullable=False)
    #relations
    item = db.relationship('Item', back_populates='locations', lazy='select')
    location = db.relationship('Location', back_populates='items', lazy='select')
    sales = db.relationship('Sale', secondary=sale_stock, back_populates='stocks', lazy='select')

    def __repr__(self) -> str:
        return f'<Item_Entry {self.id}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'input_date': self.input_date,
            'output_date': self.output_date,
            'item_cost': self.item_cost,
            'item_id': self.item_id,
            'location_id': self.location_id
        }


class Sale(db.Model):
    __tablename__ = 'sale'
    id = db.Column(db.Integer, primary_key=True)
    date_created  = db.Column(db.DateTime, default = datetime.utcnow)
    payment_method = db.Column(db.String(128))
    payment_date = db.Column(db.DateTime)
    payment_confirmed = db.Column(db.Boolean)
    shipped = db.Column(db.Boolean)
    shipped_date = db.Column(db.DateTime)
    #relations
    stocks = db.relationship('Stock', secondary=sale_stock, back_populates='sales', lazy='select')

    def __repr__(self) -> str:
        return f'<Sale id: {self.id}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'date_created': self.date_created,
            'payment_method': self.payment_method,
            'payment_date': self.payment_date,
            'payment_confirm': self.payment_confirmed,
            'sale_shipped': self.shipped,
            'shipped_date': self.shipped_date
        }


class Devolution(db.Model):
    __tablename__= 'devolution'
    id = db.Column(db.Integer, primary_key=True)
    date_requested = db.Column(db.DateTime, default = datetime.utcnow)

    def __repr__(self) -> str:
        return f'<Devolution id: {self.id}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'date_requested': self.date_requested
        }