"""Central configuration. Every secret comes from the environment — never hardcode."""
import os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


class Config:
    # Flask
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-only-change-me")
    # Render/Fly provide DATABASE_URL (postgres). Local default: sqlite file.
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", "sqlite:///" + os.path.join(BASE_DIR, "amani.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Public base URL of the deployed app, e.g. https://amani-chat.onrender.com
    # Used for Stripe success/cancel redirect URLs.
    APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:5000").rstrip("/")

    # --- OpenAI-compatible chat API ---
    OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
    OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
    OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/")

    # --- Stripe ---
    STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY", "")
    STRIPE_WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    STRIPE_PRICE_MONTHLY = os.environ.get("STRIPE_PRICE_MONTHLY", "")   # price_... $24.99/mo
    STRIPE_PRICE_METERED = os.environ.get("STRIPE_PRICE_METERED", "")    # price_... $1.00/min metered
    STRIPE_METER_EVENT_NAME = os.environ.get("STRIPE_METER_EVENT_NAME", "amani_chat_minute")

    # Pricing (display only — real charges are created in Stripe)
    PRICE_PER_MINUTE_USD = 1.00
    PRICE_MONTHLY_USD = 24.99

    # Cookies: set SECURE_COOKIES=1 in production (https)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("SECURE_COOKIES", "0") == "1"
    REMEMBER_COOKIE_DURATION = 60 * 60 * 24 * 30  # 30 days

    @property
    def ai_configured(self):
        return bool(self.OPENAI_API_KEY)

    @property
    def stripe_configured(self):
        return bool(self.STRIPE_SECRET_KEY)

    @property
    def demo_mode(self):
        return not (self.ai_configured and self.stripe_configured)
