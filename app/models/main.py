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

    def __repr__(self):
        return f"<User {self.id}>"

    def serialize(self) -> dict:
        return {
            "id": self.id,
            "fname" : self.fname,
            "lname" : self.lname,
            "image": self.image,
        }

    def serialize_all(self) -> dict:
        rsp = self.serialize()
        rsp.update({
            "since": datetime_formatter(self._registration_date),
            "phone": self.phone,
            "email": self._email
        })
        return rsp

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
    _company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    _user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    _role_function_id = db.Column(db.Integer, db.ForeignKey('role_function.id'), nullable=False)
    storages = db.Column(JSON, default={'scope': []})
    #relations
    user = db.relationship('User', back_populates='roles', lazy='joined')
    company = db.relationship('Company', back_populates='roles', lazy='joined')
    role_function = db.relationship('RoleFunction', back_populates='roles', lazy='joined')

    def __repr__(self) -> str:
        return f'<User {self.user_id} - Company {self._company_id} - Role {self._company_id}'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'relation-date': datetime_formatter(self._relation_date),
            'limited-to': self.storages.get('scope', [])
        }
    
    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            'role': self.role_function.serialize()
        }

class Company(db.Model):
    __tablename__ = 'company'
    id = db.Column(db.Integer, primary_key=True)
    _creation_date = db.Column(db.DateTime, default=datetime.utcnow)
    _plan_id = db.Column(db.Integer, db.ForeignKey('plan.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    logo = db.Column(db.String(256), default=DefaultContent().company_image)
    currency = db.Column(db.Integer, default = 0)
    tz_name = db.Column(db.String(128), default="america/caracas")
    address = db.Column(JSON, default={})
    currencies = db.Column(JSON, default={"all": [DefaultContent().currency]})
    #relationships
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
            "logo": self.logo,
        }
    
    def serialize_all(self) -> dict:
        rsp = self.serialize()
        rsp.update({
            'address': self.address, 
            'currency': self.currencies.get('all', [DefaultContent().currency])[0],
            'time-zone-name': self.tz_name
        })
        return rsp

class Storage(db.Model):
    __tablename__ = 'storage'
    id = db.Column(db.Integer, primary_key=True)
    _company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(128), nullable=True)
    code = db.Column(db.String(64), default = '')
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
            'code': f'{self.name[:3]}.{self.id:02d}' if self.code == '' else f'{self.code}.{self.id:02d}',
        }

    def serialize_all(self) -> dict:
        rsp = self.serialize()
        rsp.update({
            'address': self.address,
            'utc': {
                "latitude": self.latitude, 
                "longitude": self.longitude,
            'item-list-count': self.stock.count()
            }
        })

        return rsp


class Item(db.Model):
    __tablename__='item'
    id = db.Column(db.Integer, primary_key=True)
    _company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    _qr_code = db.Column(db.String(128))
    name = db.Column(db.String(128), nullable=False)
    sku = db.Column(db.String(64), default='')
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
    attributes = db.relationship('AttributeValue', back_populates='item', lazy='dynamic')
    orders = db.relationship('Order', back_populates='items', lazy='dynamic')


    def __repr__(self) -> str:
        return f'<Item: {self.name}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description or "",
            'sku': f'{self.category.name[:5]}.{self.name[:5]}.{self.id:04d}' if self.sku == '' else f'{self.sku}.{self.id:04d}',
            'fav-img': self.images.get('urls', [DefaultContent().item_image])[0] #return first image in json object
        }

    def serialize_all(self) -> dict:
        rsp = self.serialize()
        rsp.update({
            'unit': self.unit,
            'img': self.images.get('urls', [DefaultContent().item_image])[1:], #return all images in json object
            'category': self.category.serialize() if self.category is not None else {},
            'qr_code': self._qr_code or '',
            'sale-price': self.sale_price,
            'attributes': list(map(lambda x:x.serialize(), self.attributes)),
            'category': {**self.category.serialize(), "path": self.category.serialize_path()} if self.category is not None else {}
        })
        return rsp


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
        return f'<Category: {self.name}'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'name': self.name
        }

    def serialize_children(self) -> dict:
        return {
            **self.serialize(),
            "sub-categories": list(map(lambda x: x.serialize_children(), self.children))
        }

    def serialize_path(self) -> dict:
        path = []
        p = self.parent
        while p != None:
            path.insert(0, f'name:{p.name}-id:{p.id}')
            p = p.parent
        
        return path

    def get_all_nodes(self) -> list:
        ids = [self.id]
        for i in self.children:
            ids.append(i.id)
            if i.children != []:
                ids.extend(i.get_all_nodes())
        
        return list(set(ids))

    def get_attributes(self) -> list:
        #create function to get all attributes for a given category. must include parent attributes
        ids = [self.id]
        p = self.parent
        while p != None:
            ids.append(p.id)
            if p.parent is not None:
                ids.append(p.parent_id)
            p = p.parent

        attributes = db.session.query(Attribute).join(Attribute.categories).filter(Attribute.id.in_(ids)).all()
        return attributes


class Third(db.Model):
    __tablename__='third'
    id = db.Column(db.Integer, primary_key=True)
    _company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    addresses = db.Column(JSON, default={'all': []})
    third_type = db.Column(db.String(64), default="client")
    contacts = db.Column(JSON, default={'all': []})
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
            'type': self.type
        }

    def serialize_all(self) -> dict:
        rsp = self.serialize()
        rsp.update({
            'addresses': self.addresses,
            'contacts': self.contacts
        })

        return rsp


class Shelf(db.Model):
    __tablename__ = 'shelf'
    id = db.Column(db.Integer, primary_key=True)
    _storage_id = db.Column(db.Integer, db.ForeignKey('storage.id'), nullable=False)
    _qr_code = db.Column(db.String(128), default='')
    column = db.Column(db.Integer, default=0)
    row = db.Column(db.Integer, default=0)
    location_ref = db.Column(db.Text)
    parent_id = db.Column(db.Integer, db.ForeignKey('shelf.id'))
    #relations
    children = db.relationship('Shelf', cascade="all, delete-orphan", backref=backref('parent', remote_side=id))
    storage = db.relationship('Storage', back_populates='shelves', lazy='joined')
    inventories = db.relationship('Inventory', back_populates='shelf', lazy='dynamic')

    def __repr__(self) -> str:
        return f'<Shelf {self.id}'

    def serialize(self) -> dict:
        main_self = self.parent_id if self.parent_id is not None else self.id
        return {
            'id': self.id,
            'qr-code': self._qr_code or '',
            'location-ref': f'shelf-{main_self:04d}.column-{self.column:04d}.row-{self.row:04d}'
        }

    def serialize_path(self) -> dict:
        path = []
        p = self.parent
        while p != None:
            path.insert(0, f'name:{p.name}-id:{p.id}')
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
            'storage-limits': {'max': self.max, 'min': self.min},
            'method': self.method,
            'available': self.get_stock_value()
        }

    def get_stock_value(self) -> float:
        #todas las adquisiciones que se encuentran en el inventario.
        adquisitions = db.session.query(func.sum(Adquisition.item_qtty)).select_from(Stock).\
            join(Stock.adquisitions).join(Adquisition.inventories).\
                filter(Stock.id == self.id).scalar() or 0

        #todas las requisiciones validadas, es decir, con pago verificado o aprobados por el administrador.
        requisitions = db.session.query(func.sum(Requisition.item_qtty)).select_from(Stock).\
            join(Stock.adquisitions).join(Adquisition.inventories).join(Inventory.requisitions).\
                filter(Stock.id == self.id, Requisition.validated == True).scalar() or 0
                
        return float(adquisitions - requisitions)


class Order(db.Model):
    __tablename__ = 'order'
    id = db.Column(db.Integer, primary_key=True)
    _log = db.Column(JSON)
    _date_created = db.Column(db.DateTime, default=datetime.utcnow)
    _date_closed = db.Column(db.DateTime)
    _client_id = db.Column(db.Integer, db.ForeignKey('third.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    status = db.Column(db.String(64), default='in-review')
    payment_verified = db.Column(db.Boolean, default=False)
    delivery_address = db.Column(JSON)
    delivery_voucher = db.Column(JSON)
    #relations
    item = db.relationship('Item', back_populates='orders', lazy='select')
    requisitions = db.relationship('Requisition', back_populates='order', lazy='dynamic')
    client = db.relationship('Third', back_populates='orders', lazy='select')


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
    inventory_id = db.Column(db.Integer, db.ForeignKey('inventory.id'), nullable=False)
    item_qtty = db.Column(db.Float(precision=2), default=1.0)
    status = db.Column(db.String(32), default='in-review')
    validated = db.Column(db.Boolean, default=False)
    #relations
    order = db.relationship('Order', back_populates='requisitions', lazy='select')
    inventory = db.relationship('Inventory', back_populates='requisitions', lazy='select')

    def __repr__(self) -> str:
        return f'<Requisition id: {self.id}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'status': self.status,
            'number': f'REQ-{self.id:03d}-{self._date_created.strftime("%d.%m.%Y")}',
            'required-qtty': self.item_qtty
        }


class Adquisition(db.Model):
    __tablename__ = 'adquisition'
    id = db.Column(db.Integer, primary_key=True)
    _entry_date = db.Column(db.DateTime, default=datetime.utcnow)
    _log = db.Column(JSON)
    _stock_id = db.Column(db.Integer, db.ForeignKey('stock.id'), nullable=False)
    item_qtty = db.Column(db.Float(precision=2), default=0.0)
    unit_cost = db.Column(db.Float(precision=2), default=0.0)
    purchase_ref_num = db.Column(db.String(128))
    provider_part_code = db.Column(db.String(128))
    pkg_weight = db.Column(db.Float(precision=2), default=0.0) #kg
    pkg_volume = db.Column(db.Float(precision=2), default=0.0) #cm3
    status = db.Column(db.String(32), default='in-review')
    review_img = db.Column(JSON) #imagenes de la revision de los items.
    provider_id = db.Column(db.Integer, db.ForeignKey('third.id'))
    #relations
    provider = db.relationship('Third', back_populates='adquisitions', lazy='select')
    stock = db.relationship('Stock', back_populates='adquisitions', lazy='select')
    inventories = db.relationship('Inventory', back_populates='adquisition', lazy='dynamic')


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
    type = db.Column(db.String(32), default='string') #string - number - boolean
    #relations
    company = db.relationship('Company', back_populates='units_catalog', lazy='select')
    attribute_values = db.relationship('AttributeValue', back_populates='unit', lazy='dynamic')

    def __repr__(self) -> str:
        return f"<Unit id: {self.id}>"

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'type': self.type
        }


class Attribute(db.Model):
    __tablename__ = 'attribute'
    id = db.Column(db.Integer, primary_key=True)
    _company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    # relations
    company = db.relationship('Company', back_populates='attributes_catalog', lazy='select')
    items = db.relationship('AttributeValue', back_populates='attribute', lazy='dynamic')
    categories = db.relationship('Category', secondary=attribute_category, back_populates='attributes', lazy='select')

    def __repr__(self) -> str:
        return f'<attribute id: {self.id}>'

    def serialize(self) -> str:
        return {
            'id': self.id,
            'name': self.name
        }


class AttributeValue(db.Model):
    __tablename__ = 'attribute_value'
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.String(64), default="") #unit value for a given attribute
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    attribute_id = db.Column(db.Integer, db.ForeignKey('attribute.id'), nullable=False)
    unit_id = db.Column(db.Integer, db.ForeignKey('unit_catalog.id'))
    #relations
    item = db.relationship('Item', back_populates='attributes', lazy='select')
    attribute = db.relationship('Attribute', back_populates='items', lazy='joined')
    unit = db.relationship('UnitCatalog', back_populates='attribute_values', lazy='joined')

    def __repr__(self) -> str:
        return f'<item-id: {self.item_id} attribute-id: {self.attribute_id}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'value': self.value
        }


class Inventory(db.Model):
    __tablename__ = 'inventory'
    id = db.Column(db.Integer, primary_key=True)
    _date_created = db.Column(db.DateTime, default=datetime.utcnow)
    _log = db.Column(JSON)
    item_qtty = db.Column(db.Float(precision=2), default=1.0)
    shelf_id = db.Column(db.Integer, db.ForeignKey('shelf.id'), nullable=False)
    adquisition_id = db.Column(db.Integer, db.ForeignKey('adquisition.id'), nullable=False)
    #relations
    shelf = db.relationship('Shelf', back_populates='inventories', lazy='select')
    adquisition = db.relationship('Adquisition', back_populates='inventories', lazy='select')
    requisitions = db.relationship('Requisition', back_populates='inventory', lazy='dynamic')

    def __repr__(self) -> str:
        return f'Inventory id: <{self.id}>'

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'unit_qtty': self.item_qtty
        }