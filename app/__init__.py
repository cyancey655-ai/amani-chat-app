"""Amani Chat — Flask application factory."""
import os

from flask import Flask
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_login import LoginManager

from .config import Config
from .models import User, db

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to continue."


def _user_key():
    from flask_login import current_user

    if current_user.is_authenticated:
        return f"user:{current_user.id}"
    return get_remote_address()


limiter = Limiter(key_func=_user_key, default_limits=["600 per hour"])


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def create_app():
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_object(Config())

    # Normalize postgres URLs (Render/Heroku style)
    uri = app.config["SQLALCHEMY_DATABASE_URI"]
    if uri.startswith("postgres://"):
        app.config["SQLALCHEMY_DATABASE_URI"] = uri.replace("postgres://", "postgresql://", 1)

    db.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)

    from .routes_auth import auth_bp
    from .routes_billing import billing_bp
    from .routes_chat import chat_bp
    from .routes_main import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(billing_bp)

    @app.context_processor
    def inject_globals():
        return {
            "demo_mode": app.config["STRIPE_SECRET_KEY"] == "" or app.config["OPENAI_API_KEY"] == "",
            "ai_demo": app.config["OPENAI_API_KEY"] == "",
            "stripe_demo": app.config["STRIPE_SECRET_KEY"] == "",
        }

    with app.app_context():
        db.create_all()

    return app
