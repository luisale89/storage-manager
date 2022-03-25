from app.extensions import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSON


class Role(db.Model):
    __tablename__ = "role"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), unique=True, nullable=False)
    code = db.Column(db.String(128), unique=True, nullable=False)
    creation_date = db.Column(db.DateTime, default=datetime.utcnow)
    permits = db.Column(JSON, default={'create': True, 'read': True, 'update': True, 'delete': True})
    #relations
    user_company = db.relationship('UserCompany', back_populates='role', lazy='select')

    def __repr__(self) -> str:
        return f"<Role {self.name}>"

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'creation_date': self.creation_date,
            'permits': self.permits
        }

    def add_default_roles():
        commit = False
        admin = Role.query.filter_by(code='admin').first() #!Administrador
        if admin is None:
            admin = Role(
                name = 'Administrador', 
                code='admin'
                #default permits
            )
            
            db.session.add(admin)
            commit = True

        client = Role.query.filter_by(code='client').first() #!Cliente
        if client is None:
            client = Role(
                name='Cliente', 
                code='client',
                permits = {'create': False, 'read': True, 'update': True, 'delete': False}
            )

            db.session.add(client)
            commit = True

        provider = Role.query.filter_by(code='provider').first() #!Proveedor
        if provider is None:
            provider = Role(
                name='Proveedor', 
                code='provider',
                permits = {'create': False, 'read': True, 'update': True, 'delete': False}
            )

            db.session.add(provider)
            commit = True

        obs = Role.query.filter_by(code='obs').first() #!Observador
        if obs is None:
            obs = Role(
                name='Observador', 
                code = 'obs',
                permits = {'create': False, 'read': True, 'update': False, 'delete': False}
            )

            db.session.add(obs)
            commit = True

        if commit:
            db.session.commit()
        
        pass


class Plan(db.Model):

    __tablename__ = 'plan'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    code = db.Column(db.String(128), unique=True, nullable=False)
    creation_date = db.Column(db.DateTime, default=datetime.utcnow)
    limits = db.Column(JSON, default={'storage': 10, 'items': 100, 'provider': 10, 'client': 10, 'admin': 1})
    #relations
    companies = db.relationship('Company', back_populates='plan', lazy='select')

    def __repr__(self) -> str:
        return f"<Role {self.name}>"

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
            'creation_date': self.creation_date,
            'limits': self.limits
        }

    def add_default_plans():
        
        commit = False
        basic = Plan.query.filter_by(code='basic').first()
        if basic is None:
            basic = Plan(
                name = 'Plan Basico',
                code = 'basic'
                #default limits
            )
            
            db.session.add(basic)
            commit = True

        if commit:
            db.session.commit()

        pass


