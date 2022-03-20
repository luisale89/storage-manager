
from app.extensions import db
from datetime import datetime

from werkzeug.security import generate_password_hash
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import backref

from .global_models import (Role, Plan, Category)

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
    companies = db.relationship('UserCompany', back_populates='user', lazy=True)
    # work_relations = db.relationship('WorkRelation', back_populates='user', lazy=True)

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

    def check_user_exists(email):
        return User.query.filter_by(email=email).first()


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
    user = db.relationship('User', back_populates='companies', lazy=True)
    company = db.relationship('Company', back_populates='users', lazy=True)
    role = db.relationship('Role', back_populates='user_company', lazy=True)

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
    code = db.Column(db.String(128))
    image = db.Column(db.String(256))
    address = db.Column(JSON)
    contacts = db.Column(JSON)
    latitude = db.Column(db.Float(precision=8))
    longitude = db.Column(db.Float(precision=8))
    registration_date = db.Column(db.DateTime, default=datetime.utcnow)
    plan_id = db.Column(db.Integer, db.ForeignKey('plan.id'), nullable=False)
    #relationships
    plan = db.relationship('Plan', back_populates='companies', lazy=True)
    users = db.relationship('UserCompany', back_populates='company', lazy=True)
    # work_relations = db.relationship('WorkRelation', back_populates='company', lazy=True)
    # assets = db.relationship('Asset', back_populates='company', lazy=True)

    def __repr__(self) -> str:
        # return '<Company %r>' % self.id
        return f"<Company {self.id}>"

    def serialize(self) -> dict:
        return {
            "name": self.name,
            "code": self.code,
            "image": self.image if self.image is not None else "https://server.com/default.png",
            "address": self.address,
            "contacts": self.contacts,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "registration_date": self.registration_date
        }


