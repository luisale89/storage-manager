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
            'role_functionID': self.id,
            'role_function_name': self.name,
            'role_function_code': self.code,
            'role_function_description': self.description
        }

    @classmethod
    def get_rolefunc_by_id(cls, _id:int):
        """get role function instance by id"""
        return db.session.query(cls).get(_id)

    @classmethod
    def get_rolefunc_by_code(cls, code):
        """get role_function instance by code"""
        return db.session.query(cls).filter(cls.code == code).first()

    @classmethod
    def add_default_functions(cls):
        commit = False
        owner = cls.get_rolefunc_by_code("owner") #!Propietario
        if owner is None:
            owner = cls(
                name = 'propietario',
                code='owner',
                description='puede administrar todos los aspectos de la aplicacion.'
                #default level
            )
            
            db.session.add(owner)
            commit = True

        admin = cls.get_rolefunc_by_code("admin") #!Administrador
        if admin is None:
            admin = cls(
                name='administrador', 
                code = 'admin',
                description='puede administrar algunos aspectos de la aplicacion.',
                level=1
            )

            db.session.add(admin)
            commit = True

        oper = cls.get_rolefunc_by_code("operator") #!operador
        if oper is None:
            oper = cls(
                name='operador',
                code='operator',
                description='puede realiar acciones asignadas por los usuarios administradores',
                level=2
            )
            db.session.add(oper)
            commit=True

        obs = cls.get_rolefunc_by_code("viewer") #!observador
        if obs is None:
            obs = cls(
                name='Espectador',
                code='viewer',
                description='usuario con permisos de solo lectura',
                level=3
            )
            db.session.add(obs)
            commit=True

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
            'plan_ID': self.id,
            'plan_name': self.name,
            'plan_code': self.code,
            'plan_limits': self.limits
        }

    @classmethod
    def get_plan_by_code(cls, code):
        """get plan instance by code parameter"""
        return db.session.query(cls).filter(cls.code == code).first()

    @classmethod
    def add_default_plans(cls):
        commit = False
        basic = cls.query.filter_by(code='basic').first()
        if basic is None:
            basic = cls(
                name = 'Plan Basico',
                code = 'basic'
                #default limits
            )
            
            db.session.add(basic)
            commit = True

        free = cls.get_plan_by_code("free")
        if free is None:
            free = cls(
                name = 'Plan Gratuito',
                code = 'free',
                limits = {'storage': 1, 'items': 10, 'users': 1}
            )
            db.session.add(free)
            commit = True
        
        if commit:
            db.session.commit()

        pass


