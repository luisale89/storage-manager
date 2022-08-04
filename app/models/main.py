from app.extensions import db
from datetime import datetime, timedelta
from typing import Union

from werkzeug.security import generate_password_hash
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import backref
from sqlalchemy import func
from sqlalchemy.types import Interval

#utils
from app.utils.helpers import DefaultContent, DateTimeHelpers, QR_factory

#models
from .global_models import *
from .assoc_models import attribute_category, attributeValue_item


class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    _email = db.Column(db.String(256), unique=True, nullable=False)
    _password_hash = db.Column(db.String(256), nullable=False)
    _registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    _email_confirmed = db.Column(db.Boolean, default=False)
    _signup_completed = db.Column(db.Boolean, default=False)
    _image = db.Column(db.String(256), default=DefaultContent().user_image)
    fname = db.Column(db.String(128), default='')
    lname = db.Column(db.String(128), default='')
    phone = db.Column(db.String(32), default='')
    #relations
    roles = db.relationship('Role', back_populates='user', lazy='dynamic')

    def __repr__(self):
        return f"User(email={self.email})"

    @property
    def image(self):
        return self._image

    def serialize(self) -> dict:
        return {
            "user_ID": self.id,
            "user_fisrtName" : self.fname,
            "user_lastName" : self.lname,
            "user_image": self.image
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            "user_since": DateTimeHelpers(self._registration_date).datetime_formatter(),
            "user_phone": self.phone,
            "user_email": self.email
        }

    def serialize_public_info(self) -> dict:
        return {
            'user_companies': list(map(lambda x: {'company_name': x.company.name, 'company_ID': x.company.id}, filter(lambda x: x.is_enabled(), self.roles.all()))),
            'user_signupCompleted': self.is_enabled()
        }

    @classmethod
    def get_user_by_email(cls, email:str):
        """get user in the database by email"""
        return db.session.query(cls).filter(cls._email == email).first()

    @classmethod
    def get_user_by_id(cls, _id):
        """
        get user in the database by id
        - id parameter must be a positive integer value
        """
        return db.session.query(cls).get(_id)

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

    @property
    def email_confirmed(self):
        return self._email_confirmed

    @email_confirmed.setter
    def email_confirmed(self, new_state:bool):
        self._email_confirmed = new_state

    @property
    def signup_completed(self):
        return self._signup_completed

    @signup_completed.setter
    def signup_completed(self, new_state:bool):
        self._signup_completed = new_state

    def is_enabled(self):
        return True if self.email_confirmed and self.signup_completed else False


class Role(db.Model):
    __tablename__ = 'role'
    id = db.Column(db.Integer, primary_key=True)
    _relation_date = db.Column(db.DateTime, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    _inv_accepted = db.Column(db.Boolean, default=False)
    _isActive = db.Column(db.Boolean, default=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    role_function_id = db.Column(db.Integer, db.ForeignKey('role_function.id'), nullable=False)
    #relations
    user = db.relationship('User', back_populates='roles', lazy='joined')
    company = db.relationship('Company', back_populates='roles', lazy='joined')
    role_function = db.relationship('RoleFunction', back_populates='roles', lazy='joined')

    def __repr__(self) -> str:
        return f'Role(id={self.id})'

    @property
    def is_active(self):
        return self._isActive

    @is_active.setter
    def is_active(self, new_state:bool):
        self._isActive = new_state

    @property
    def inv_accepted(self):
        return self._inv_accepted

    @inv_accepted.setter
    def inv_accepted(self, new_state:bool):
        self._inv_accepted = new_state

    def is_enabled(self):
        return True if self.is_active and self.inv_accepted else False

    def serialize(self) -> dict:
        return {
            'role_ID': self.id,
            'role_relationDate': DateTimeHelpers(self._relation_date).datetime_formatter(),
            'role_isActive': self.is_active,
            'role_accepted': self.inv_accepted,
            "role_function": self.role_function.serialize(),
        }
    
    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            "role_user": self.user.serialize(),
            "role_company": self.company.serialize()
        }

    @classmethod
    def get_role_by_id(cls, _id):
        """get Role instance by id"""
        return db.session.query(cls).get(_id)

    @classmethod
    def get_relation_user_company(cls, user_id, company_id):
        """return role between an user and company"""

        return db.session.query(cls).join(cls.user).join(cls.company).\
            filter(User.id==user_id, Company.id==company_id).first()


class Company(db.Model):
    __tablename__ = 'company'
    id = db.Column(db.Integer, primary_key=True)
    _creation_date = db.Column(db.DateTime, default=datetime.utcnow)
    _logo = db.Column(db.String(256), default=DefaultContent().company_image)
    plan_id = db.Column(db.Integer, db.ForeignKey('plan.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    tz_name = db.Column(db.String(128), default="america/caracas")
    address = db.Column(JSON, default={'address': {}})
    currency = db.Column(JSON, default={"currency": DefaultContent().currency})
    #relationships
    plan = db.relationship('Plan', back_populates='companies', lazy='joined')
    roles = db.relationship('Role', back_populates='company', lazy='dynamic')
    storages = db.relationship('Storage', back_populates='company', lazy='dynamic')
    items = db.relationship('Item', back_populates='company', lazy='dynamic')
    supply_requests = db.relationship("SupplyRequest", back_populates="company", lazy="dynamic")
    order_requests = db.relationship("OrderRequest", back_populates="company", lazy="dynamic")
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
            "company_ID": self.id,
            "company_name": self.name,
            "company_logo": self.logo,
        }
    
    def serialize_all(self) -> dict:
        return{
            **self.serialize(),
            'company_address': self.address.get("address", {}),
            'company_currency': self.currency.get("currency", {}),
            'company_timezone': self.tz_name,
            'company_plan': self.plan.serialize()
        }

    @classmethod
    def get_company_by_id(cls, company_id:int):
        """get Company instance on company_id parameter"""
        return db.session.query(cls).get(company_id)

    def get_category_by_id(self, category_id:int):
        """get category instance related to self.id using category_id parameter"""
        return self.categories.filter(Category.id == category_id).first()

    def get_storage_by_id(self, storage_id:int):
        """get storage instance related to current company instance, using identifier"""
        return self.storages.filter(Storage.id == storage_id).first()

    def get_item_by_id(self, item_id:int):
        """get item instance related with current company, using identifier"""
        return self.items.filter(Item.id == item_id).first()

    def get_provider(self, provider_id:int):
        """get provider instance related to current company instance"""
        return self.providers.filter(Provider.id == provider_id).first()

    def get_attribute(self, att_id:int):
        """get attribute instance related to current company instance"""
        return self.attributes.filter(Attribute.id == att_id).first()


class Storage(db.Model):
    __tablename__ = 'storage'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(128), default="")
    address = db.Column(JSON, default={'address': {}})
    latitude = db.Column(db.Float(precision=6), default=0.0)
    longitude = db.Column(db.Float(precision=6), default=0.0)
    #relations
    company = db.relationship('Company', back_populates='storages', lazy='joined')
    containers = db.relationship('Container', back_populates='storage', lazy='dynamic')
    supply_requests = db.relationship("SupplyRequest", back_populates="storage", lazy="dynamic")

    def __repr__(self) -> str:
        return f'Storage(name={self.name})'

    def serialize(self):
        return {
            'storage_ID': self.id,
            'storage_name': self.name
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            **self.address,
            'storage_utc': {
                "latitude": self.latitude, 
                "longitude": self.longitude
            },
            'storage_containers_count': self.containers.count(),
            'storage_supplyRequests_count': self.supply_requests.count(),
            'storage_company': self.company.serialize()
        }

    def get_container(self, container_id:int):
        """get container instance by its id"""
        return self.containers.filter(Container.id == container_id).first()


class Item(db.Model):
    def __init__(self, *args, **kwargs) -> None:
        """update kwargs arguments with the last qr_code counter in the company"""
        company_id = kwargs.get("company_id", None)
        if company_id and isinstance(company_id, int):
            last_item = db.session.query(Item).filter(Item.company_id == company_id).\
                order_by(Item._correlative.desc()).first()
            if not last_item:
                kwargs.update({"_correlative": 1})
            else:
                kwargs.update({"_correlative": last_item._correlative+1})

        super().__init__(*args, **kwargs)

    __tablename__='item'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    _images = db.Column(JSON, default={'images': [DefaultContent().item_image]})
    _correlative = db.Column(db.Integer, default=0)
    sku = db.Column(db.String(64), default='')
    name = db.Column(db.String(128), nullable=False)
    pkg_weight = db.Column(db.Float(precision=2), default=0.0) #kg
    pkg_sizes = db.Column(JSON, default={"pkg_sizes": {"length":  0, "width": 0, "height": 0}})
    description = db.Column(db.Text)
    sale_unit = db.Column(db.String(128))
    sale_price = db.Column(db.Float(precision=2), default=0.0)
    category_id = db.Column(db.Integer, db.ForeignKey('category.id'), nullable=False)
    #relations
    company = db.relationship('Company', back_populates='items', lazy='joined')
    category = db.relationship('Category', back_populates='items', lazy='joined')
    acquisitions = db.relationship("Acquisition", back_populates="item", lazy="dynamic")
    attribute_values = db.relationship('AttributeValue', secondary=attributeValue_item, back_populates='items', lazy='dynamic')
    orders = db.relationship('Order', back_populates='item', lazy='dynamic')

    def __repr__(self) -> str:
        return f'Item(id={self.id})'

    @property
    def images(self):
        return self._images

    def serialize(self) -> dict:
        return {
            'item_images': self.images.get("images", {}),
            'item_ID': self.id,
            'item_name': self.name,
            'item_description': self.description or "",
            'item_sku': self.sku
        }

    def serialize_attributes(self) -> dict:
        attributes = self.category.get_attributes()
        return {
            'item_attributes': list(map(lambda x:x.serialize_with_item(self.id), attributes))
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            **self.serialize_attributes(),
            "item_pkg_sizes": self.pkg_sizes.get("pkg_sizes", {}),
            "item_pkg_weight": self.pkg_weight,
            'item_unit': self.sale_unit,
            'item_price': {"amount": self.sale_price, "symbol": "USD"},
            "item_company": self.company.serialize(),
            'item_category': {
                **self.category.serialize(), 
                "path": self.category.serialize_path()
            },
            'item_acquisitions_count': self.acquisitions.count(),
            'item_orders_count': self.orders.count(),
            'item_stock': self.stock,
            'item_avrg_cost': self.avrg_cost
        }

    @property
    def stock(self):
        """get the current stock of the instance"""
        stock = db.session.query(func.sum(Acquisition.item_qtty)).select_from(Item).join(Item.acquisitions).\
            join(Acquisition.inventories).outerjoin(Inventory.order).\
                filter(Item.id == self.id, Inventory.order == None).scalar() or 0.0

        return stock

    @property
    def avrg_cost(self):
        acq = db.session.query(Acquisition.item_qtty, Acquisition.item_cost).select_from(Item).\
            join(Item.acquisitions).join(Acquisition.inventories).\
                filter(Item.id == self.id).all()
        if not acq:
            return 0.0

        numerator = sum([(x * y) for x,y in acq])
        denominator = sum([x[0] for x in acq])
        if not denominator:
            return 0.0
        
        return round(numerator/denominator, 2)


class Category(db.Model):
    __tablename__= 'category'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey('category.id'))
    #relations
    children = db.relationship('Category', cascade="all, delete-orphan", backref=backref('parent', remote_side=id))
    company = db.relationship('Company', back_populates='categories', lazy='joined')
    items = db.relationship('Item', back_populates='category', lazy='dynamic')
    attributes = db.relationship('Attribute', secondary=attribute_category, back_populates='categories', lazy='dynamic')

    
    def __repr__(self) -> str:
        return f'Category(name={self.name})'

    def serialize(self) -> dict:
        return {
            'category_ID': self.id,
            'category_name': self.name
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            "category_path": self.serialize_path(), 
            "category_children": list(map(lambda x: x.serialize(), self.children)),
            "category_attributes": list(map(lambda x: x.serialize(), self.get_attributes())),
            "category_company": self.company.serialize()
        }

    def serialize_children(self) -> dict:
        return {
            **self.serialize(),
            "category_childs": list(map(lambda x: x.serialize_children(), self.children))
        }

    def serialize_path(self) -> list:
        """serialize the path to root of current category"""
        path = []
        p = self.parent
        while p is not None:
            path.insert(0, {"category_name": p.name, "category_id": p.id})
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

    def get_attributes(self, return_ids:bool=False) -> list:
        """function that returns a list with all the attributes of the current category and its ascendat categories"""
        ids = [self.id]
        p = self.parent
        while p is not None:
            ids.append(p.id)
            if p.parent is not None:
                ids.append(p.parent_id)
            p = p.parent
        
        if return_ids:
            return ids

        return db.session.query(Attribute).join(Attribute.categories).filter(Category.id.in_(ids)).all()

    def get_attribute_by_id(self, att_id:int):
        """get attribute instance related to current category"""
        self.attributes.filter(Attribute.id == att_id).first()


class Provider(db.Model):
    __tablename__='provider'
    id = db.Column(db.Integer, primary_key=-True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(64), nullable=False)
    contacts = db.Column(JSON, default={'contacts': []})
    address = db.Column(JSON, default={'address': {}})
    #relations
    company = db.relationship('Company', back_populates='providers', lazy='joined')
    acquisitions = db.relationship("Acquisition", back_populates="provider", lazy="dynamic")

    def __repr__(self) -> str:
        return f'Provider(name={self.name})'

    def serialize(self) -> dict:
        return {
            'provider_ID': self.id,
            'provider_name': self.name
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            'provider_contacts': self.contacts.get("contacts", []),
            'provider_address': self.address.get("address", {}),
            'provider_company': self.company.serialize()
        }


class OrderRequest(db.Model):
    def __init__(self, *args, **kwargs) -> None:
        """update kwargs arguments with the last qr_code counter in the company"""
        company_id = kwargs.get("company_id", None)
        if company_id and isinstance(company_id, int):
            last_request = db.session.query(OrderRequest).filter(OrderRequest.company_id == company_id).\
                order_by(OrderRequest._correlative.desc()).first()
            if not last_request:
                kwargs.update({"_correlative": 1})
            else:
                kwargs.update({"_correlative": last_request._correlative+1})

        super().__init__(*args, **kwargs)

    __tablename__ = 'order_request'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False) #provider
    _creation_date = db.Column(db.DateTime, default=datetime.utcnow)
    _exp_timedelta = db.Column(Interval, default=lambda:timedelta(days=15)) #time to confirm the payment
    _payment_confirmed = db.Column(db.Boolean, default=False)
    _payment_date = db.Column(db.DateTime)
    _shipping_date = db.Column(db.DateTime)
    _shipping_confirmed = db.Column(db.Boolean, default=False)
    _correlative = db.Column(db.Integer, default=0)
    _type = db.Column(db.String(32), default="sale") #2 types: sale, reserve
    shipping_address = db.Column(JSON, default={'shipping_address': {}})
    #relations
    company = db.relationship("Company", back_populates="order_requests", lazy="joined")
    orders = db.relationship('Order', back_populates='order_request', lazy='dynamic')

    def __repr__(self) -> str:
        return f'PurchasOrder(id={self.id})'

    def serialize(self) -> dict:
        return {
            'OR_ID': self.id,
            'OR_code': self.get_code(),
            'OR_paymentConfirmed': self._payment_confirmed,
            'OR_shipped': self._shipping_confirmed,
            'OR_type': self._type
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            'OR_company': self.company.serialize(),
            'OR_dateCreated': DateTimeHelpers(self._creation_date).datetime_formatter(),
            'OR_dueDate': DateTimeHelpers(self._creation_date + self._exp_timedelta).datetime_formatter(),
            'OR_paymentDate': self._payment_confirmed or '',
            'OR_shippingDate': self._shipping_date or '',
            'OR_shippingAddress': self.shipping_address.get("shipping_address", {})
        }

    @property
    def payment_confirmed(self):
        return self._payment_confirmed

    @payment_confirmed.setter
    def payment_confirmed(self, confirmed:bool):
        self._payment_confirmed = confirmed
        if confirmed:
            self._payment_date = datetime.utcnow()

    def get_code(self):
        return f"OR.{self._correlative:02d}.{self.id:02d}"
    
    @staticmethod
    def parse_code(raw_code:str) -> Union[int, None]:
        """return order id by its code"""
        try:
            return int(raw_code.split(".")[2])
        except Exception:
            return None


class Order(db.Model):
    __tablename__ = 'order'
    id = db.Column(db.Integer, primary_key=True)
    _item_cost = db.Column(db.Float(precision=2), default=0.0)
    ordrq_id = db.Column(db.Integer, db.ForeignKey('order_request.id'), nullable=False)
    item_id = db.Column(db.Integer, db.ForeignKey('item.id'), nullable=False)
    item_qtty = db.Column(db.Float(precision=2), default=1.0)
    #relations
    item = db.relationship('Item', back_populates='orders', lazy='joined')
    inventories = db.relationship("Inventory", back_populates="order", lazy="dynamic")
    order_request = db.relationship('OrderRequest', back_populates='orders', lazy='joined')

    def __repr__(self) -> str:
        return f'Order(id={self.id})'

    def serialize(self) -> dict:
        return {
            "order_ID": self.id,
            "order_item_qty": self.item_qtty,
            "order_item_cost": self._item_cost,
            "order_inventories_count": self.inventories.count()
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            "order_item": self.item.serialize(),
            "order_request": self.order_request.serialize()
        }

    @property
    def item_cost(self):
        return self._item_cost

    @item_cost.setter
    def item_cost(self, new_cost:float):
        self._item_cost = new_cost


class SupplyRequest(db.Model):
    def __init__(self, *args, **kwargs) -> None:
        """update kwargs arguments with the last qr_code counter in the company"""
        company_id = kwargs.get("company_id", None)
        if company_id and isinstance(company_id, int):
            last_request = db.session.query(SupplyRequest).filter(SupplyRequest.company_id == company_id).\
                order_by(SupplyRequest._correlative.desc()).first()
            if not last_request:
                kwargs.update({"_correlative": 1})
            else:
                kwargs.update({"_correlative": last_request._correlative+1})

        super().__init__(*args, **kwargs)

    __tablename__ = "supply_request"
    id = db.Column(db.Integer, primary_key=True)
    _date_created = db.Column(db.DateTime, default=datetime.utcnow)
    _exp_timedelta = db.Column(Interval, default=lambda:timedelta(days=15))
    _correlative = db.Column(db.Integer, default=0)
    description = db.Column(db.Text)
    company_id = db.Column(db.Integer, db.ForeignKey("company.id"), nullable=False)
    storage_id = db.Column(db.Integer, db.ForeignKey("storage.id"), nullable=False)
    #relations
    company = db.relationship("Company", back_populates="supply_requests", lazy="joined")
    storage = db.relationship("Storage", back_populates="supply_requests", lazy="joined")
    acquisitions = db.relationship("Acquisition", back_populates="supply_request", lazy="dynamic")

    def __repr__(self) -> str:
        return f"SupplyRequest(id={self.id})"

    def serialize(self) -> dict:
        return {
            "SR_ID": self.id,
            "SR_code": self.get_code(),
            "SR_description": self.description
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            'SR_dateCreated': DateTimeHelpers(self._date_created).datetime_formatter(),
            'SR_dueDate': DateTimeHelpers(self._date_created + self._exp_timedelta).datetime_formatter(),
            'SR_company': self.company.serialize(),
            'SR_storage': self.storage.serialize()
        }

    def get_code(self) -> str:
        return f"SR.{self._correlative:02d}.{self.id:02d}"

    @staticmethod
    def parse_code(raw_code:str) -> Union[int, None]:
        try:
            return int(raw_code.split(".")[2])
        except:
            return None


class Acquisition(db.Model):
    __tablename__ = 'acquisition'
    id = db.Column(db.Integer, primary_key=True)
    _received = db.Column(db.Boolean, default=False)
    _received_date = db.Column(db.DateTime)
    provider_id = db.Column(db.Integer, db.ForeignKey("provider.id"))
    item_id = db.Column(db.Integer, db.ForeignKey("item.id"), nullable=False)
    supply_request_id = db.Column(db.Integer, db.ForeignKey("supply_request.id"))
    item_qtty = db.Column(db.Float(precision=2), default=0.0)
    item_cost = db.Column(db.Float(precision=2), default=0.0)
    provider_part_code = db.Column(db.String(128))
    #relations
    item = db.relationship("Item", back_populates="acquisitions", lazy="joined")
    supply_request = db.relationship("SupplyRequest", back_populates="acquisitions", lazy="joined")
    provider = db.relationship("Provider", back_populates="acquisitions", lazy="joined")
    inventories = db.relationship('Inventory', back_populates='acquisition', lazy='dynamic')

    def __repr__(self) -> str:
        return f'Acquisition(id={self.id})'

    def serialize(self) -> dict:
        return {
            'acquisition_ID': self.id,
            'acquisition_item_qty': self.item_qtty,
            'acquisition_received': self._received,
            "acquisition_totalCost": self.item_qtty * self.item_cost,
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            "acquisition_receivedDateTime": DateTimeHelpers(self._received_date).datetime_formatter()\
                if self._received_date else "",
            "acquisition_item_unitCost": self.item_cost,
            "acquisition_supplyRequest": self.supply_request.serialize() if self.supply_request else {},
            "acquisition_provider": self.provider.serialize() if self.provider else {},
            "acquisition_inventories_count": self.inventories.count(),
            "acquisition_remaining": self.item_qtty - self.inventories.count(),
            "acquisition_item": self.item.serialize()
        }

    @property
    def received(self):
        return self._received

    @received.setter
    def received(self):
        self._received = True
        self._received_date = datetime.utcnow()


class Attribute(db.Model):
    __tablename__ = 'attribute'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    name = db.Column(db.String(128), nullable=False)
    # relations
    company = db.relationship('Company', back_populates='attributes', lazy='joined')
    attribute_values = db.relationship('AttributeValue', back_populates='attribute', lazy='dynamic')
    categories = db.relationship('Category', secondary=attribute_category, back_populates='attributes', lazy='select')

    def __repr__(self) -> str:
        return f'Attribute(name={self.name})'

    def serialize(self) -> dict:
        return {
            'attribute_ID': self.id,
            'attribute_name': self.name
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            'attribute_company': self.company.serialize(),
            'attribute_values_count': self.attribute_values.count()
        }

    def serialize_with_item(self, target_item) -> dict:
        attr_value = self.attribute_values.join(AttributeValue.items).filter(Item.id == target_item).first()
        resp = {**self.serialize()}
        if attr_value:
            resp.update({**attr_value.serialize()})
        return resp


class AttributeValue(db.Model):
    __tablename__ = 'attribute_value'
    id = db.Column(db.Integer, primary_key=True)
    value = db.Column(db.String(64), default="") #unit value for a given attribute
    attribute_id = db.Column(db.Integer, db.ForeignKey('attribute.id'), nullable=False)
    #relations
    items = db.relationship('Item', secondary=attributeValue_item, back_populates='attribute_values', lazy='dynamic')
    attribute = db.relationship('Attribute', back_populates='attribute_values', lazy='joined')

    def __repr__(self) -> str:
        return f'AttributeValue(attribute={self.attribute.name}, value={self.value})'

    def serialize(self) -> dict:
        return {
            'attributeValue_ID': self.id,
            'attributeValue_name': self.value
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            **self.attribute.serialize(),
            'attribute': self.attribute.serialize(),
        }


class Container(db.Model):
    __tablename__ = 'container'
    id = db.Column(db.Integer, primary_key=True)
    qr_code_id = db.Column(db.Integer, db.ForeignKey('qr_code.id'), nullable=False)
    storage_id = db.Column(db.Integer, db.ForeignKey('storage.id'), nullable=False)
    description = db.Column(db.Text, default="CNT")
    location_description = db.Column(db.Text, default="")
    #relations
    storage = db.relationship('Storage', back_populates='containers', lazy='joined')
    inventories = db.relationship('Inventory', back_populates='container', lazy='dynamic')
    qr_code = db.relationship('QRCode', back_populates='container', lazy='joined')

    def __repr__(self) -> str:
        return f'Container(id={self.id})'

    def get_code(self):
        return f"CNT.{self.description[:3].upper()}.{self.id:02d}"

    @staticmethod
    def parse_code(raw_code:str) -> int:
        try:
            return int(raw_code.split(".")[2])
        except:
            return None

    def serialize(self) -> dict:
        return {
            'container_ID': self.id,
            'container_code': self.get_code(),
            'container_description': self.description,
            'container_location': self.location_description
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            'container_items_count': self.inventories.count(),
            'container_QRCode': self.qr_code.serialize(),
            'container_storage': self.storage.serialize()
        }


class Inventory(db.Model):
    __tablename__ = 'inventory'
    id = db.Column(db.Integer, primary_key=True)
    _date_created = db.Column(db.DateTime, default=datetime.utcnow)
    container_id = db.Column(db.Integer, db.ForeignKey('container.id'), nullable=False)
    acquisition_id = db.Column(db.Integer, db.ForeignKey('acquisition.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'))
    #relations
    container = db.relationship('Container', back_populates='inventories', lazy='joined')
    acquisition = db.relationship('Acquisition', back_populates='inventories', lazy='joined')
    order = db.relationship('Order', back_populates='inventories', lazy='joined')

    def __repr__(self) -> str:
        return f'Inventory(id={self.id})'

    def serialize(self) -> dict:
        return {
            'inventory_ID': self.id,
            'inventory_dateCreated': DateTimeHelpers(self._date_created).datetime_formatter()
        }

    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            'inventory_container': self.container.serialize(),
            'inventory_acquistion': self.acquisition.serialize(),
            'inventory_order': self.order.serialize() or {}
        }

    def is_available(self):
        return False if self.order else True


class QRCode(db.Model):
    def __init__(self, *args, **kwargs) -> None:
        """update kwargs arguments with the last qr_code counter in the company"""
        company_id = kwargs.get("company_id", None)
        if company_id and isinstance(company_id, int):
            last_qr = db.session.query(QRCode).filter(QRCode.company_id == company_id).\
                order_by(QRCode._correlative.desc()).first()
            if not last_qr:
                kwargs.update({"_correlative": 1})
            else:
                kwargs.update({"_correlative": last_qr._correlative+1})

        super().__init__(*args, **kwargs)

    __tablename__ = 'qr_code'
    id = db.Column(db.Integer, primary_key=True)
    _date_created = db.Column(db.DateTime, default=datetime.utcnow)
    company_id = db.Column(db.Integer, db.ForeignKey('company.id'), nullable=False)
    _correlative = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    #relations
    company = db.relationship('Company', back_populates='qr_codes', lazy='joined')
    container = db.relationship('Container', back_populates='qr_code', uselist=False, lazy='select')

    def __repr__(self) -> str:
        return f'QRCode(id={self.id})'


    def serialize(self) -> dict:
        return {
            'qrcode_dateCreated': DateTimeHelpers(self._date_created).datetime_formatter(),
            'qrcode_isActive': self.is_active,
            'qrcode_text': QR_factory(data=f"{self.id:02d}").encode,
            'qrcode_key': f"{self.company.id:02d}.{self._correlative:02d}",
            'qrcode_isUsed': self.is_used
        }


    def serialize_all(self) -> dict:
        return {
            **self.serialize(),
            'qrcode_company': self.company.serialize(),
            'qrcode_container_assigned': self.container.serialize() or {}
        }

    @property
    def is_used(self) -> bool:
        """functions return True if the QRCode instance is already assigned, else return False"""
        if self.container:
            return True

        return False


    @staticmethod
    def parse_qr(raw_qrcode:str) -> Union[int, None]:
        """get qr-id value from a valid formatted qr-string
        parameters: raw_qrcode:str (valid formatted qr-string)

        returns int(0) if parser fails
        returns int(id) for valid formatted qr-string
        """
        return QR_factory(data=raw_qrcode).decode