from app.extensions import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSON


class RoleFunction(db.Model):
    __tablename__ = "role_function"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128))
    code = db.Column(db.String(128), unique=True, nullable=False)
    _creation_date = db.Column(db.DateTime, default=datetime.utcnow)
    permits = db.Column(JSON, default={'create': True, 'read': True, 'update': True, 'delete': True})
    #relations
    roles = db.relationship('Role', back_populates='role_function', lazy='dynamic')

    def __repr__(self) -> str:
        return f"<Role {self.name}>"

    def serialize(self) -> dict:
        return {
            'name': self.name,
            'permits': self.permits
        }

    def add_default_functions():
        commit = False
        admin = RoleFunction.query.filter_by(code='admin').first() #!Administrador
        if admin is None:
            admin = RoleFunction(
                name = 'Administrador', 
                code='admin'
                #default RoleFunctions
            )
            
            db.session.add(admin)
            commit = True

        obs = RoleFunction.query.filter_by(code='obs').first() #!Observador
        if obs is None:
            obs = RoleFunction(
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
    review_date = db.Column(db.DateTime, default=datetime.utcnow)
    limits = db.Column(JSON, default={'storage': 10, 'items': 100, 'collaborators': 20})
    #relations
    companies = db.relationship('Company', back_populates='plan', lazy='dynamic')

    def __repr__(self) -> str:
        return f"<Plan name {self.name}>"

    def serialize(self) -> dict:
        return {
            'id': self.id,
            'name': self.name,
            'code': self.code,
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

        free = Plan.query.filter_by(code='free').first()
        if free is None:
            free = Plan(
                name = 'Plan Gratuito',
                code = 'free',
                limits = {'storage': 1, 'items': 10, 'collaborators': 0}
            )
            db.session.add(free)
            commit = True
        
        if commit:
            db.session.commit()

        pass


