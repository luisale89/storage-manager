from app.extensions import db
from datetime import datetime
from sqlalchemy.dialects.postgresql import JSON


class RoleFunction(db.Model):
    __tablename__ = "role_function"
    id = db.Column(db.Integer, primary_key=True)
    _created_at = db.Column(db.DateTime, default=datetime.utcnow)
    name = db.Column(db.String(128))
    code = db.Column(db.String(128), unique=True, nullable=False)
    description = db.Column(db.Text)
    level = db.Column(db.Integer, default=0)
    #relations
    roles = db.relationship('Role', back_populates='role_function', lazy='dynamic')

    def __repr__(self) -> str:
        return f"<Role {self.name}>"

    def serialize(self) -> dict:
        return {
            'name': self.name,
            'code': self.code,
            'description': self.description
        }

    def add_default_functions():
        commit = False
        owner = RoleFunction.query.filter_by(code='owner').first() #!Administrador
        if owner is None:
            owner = RoleFunction(
                name = 'propietario',
                code='owner',
                description='puede administrar todos los aspectos de la aplicacion.'
                #default RoleFunctions
            )
            
            db.session.add(owner)
            commit = True

        admin = RoleFunction.query.filter_by(code='admin').first() #!Observador
        if admin is None:
            admin = RoleFunction(
                name='administrador', 
                code = 'admin',
                description='puede administrar algunos aspectos de la aplicacion.',
                level=1
            )

            db.session.add(admin)
            commit = True

        oper = RoleFunction.query.filter_by(code='operator').first()
        if oper is None:
            oper = RoleFunction(
                name='operador',
                code='operator',
                description='solo puede realiar acciones asignadas por los usuarios administradores',
                level=2
            )

        if commit:
            db.session.commit()
        
        pass


class Plan(db.Model):

    __tablename__ = 'plan'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False, unique=True)
    code = db.Column(db.String(128), unique=True, nullable=False)
    review_date = db.Column(db.DateTime, default=datetime.utcnow)
    limits = db.Column(JSON, default={'storage': 1, 'items': 100, 'users': 10})
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
                limits = {'storage': 1, 'items': 10, 'users': 1}
            )
            db.session.add(free)
            commit = True
        
        if commit:
            db.session.commit()

        pass


