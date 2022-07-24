from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_sqlalchemy import SQLAlchemy
from flask_cors import CORS

migrate = Migrate()
db = SQLAlchemy()
jwt = JWTManager()
cors = CORS()