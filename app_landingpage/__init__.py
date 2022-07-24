import os
from flask import Flask, render_template
from app_landingpage.extensions import assets

def create_app(test_config=None):
    app = Flask(__name__)
    if test_config:
        app.config.from_object(os.environ["LANDING_SETTINGS"])

    assets.init_app(app)

    @app.route('/')
    def index():
        return render_template("index.html")

    return app