import os

from flask import Flask

from .config import DEFAULT_SECRET_KEY, STATIC_FOLDER, TEMPLATE_FOLDER
from .routes import register_routes
from .runtime import ensure_runtime_ready


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(TEMPLATE_FOLDER),
        static_folder=str(STATIC_FOLDER),
    )
    app.secret_key = os.environ.get("FLASK_SECRET_KEY", DEFAULT_SECRET_KEY)
    register_routes(app)
    ensure_runtime_ready()
    return app


app = create_app()
