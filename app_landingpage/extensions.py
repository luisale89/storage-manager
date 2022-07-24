from flask_assets import Environment

from .utils.assets import bundles

assets = Environment()
assets.register(bundles)