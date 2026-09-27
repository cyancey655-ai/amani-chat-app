"""Database models: users, conversations, messages, per-minute usage."""
from datetime import datetime, timezone

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import check_password_hash, generate_password_hash

db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc)


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)

    # Stripe linkage
    stripe_customer_id = db.Column(db.String(255), nullable=True)
    stripe_subscription_id = db.Column(db.String(255), nullable=True)

    # plan: 'none' | 'monthly' | 'metered'
    plan = db.Column(db.String(20), default="none", nullable=False)
    # plan_status: 'inactive' | 'active' | 'past_due' | 'canceled'
    plan_status = db.Column(db.String(20), default="inactive", nullable=False)

    # Demo-mode stand-in (never a real charge)
    demo_plan = db.Column(db.String(20), default="none", nullable=False)  # 'none'|'monthly'|'metered'

    def set_password(self, password: str):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)

    @property
    def is_subscriber(self) -> bool:
        """$24.99/mo unlimited — no per-minute charge."""
        if self.demo_plan == "monthly":
            return True
        return self.plan == "monthly" and self.plan_status == "active"

    @property
    def is_metered(self) -> bool:
        """$1/started minute pay-as-you-go."""
        if self.demo_plan == "metered":
            return True
        return self.plan == "metered" and self.plan_status in ("active", "past_due")

    @property
    def can_chat(self) -> bool:
        return self.is_subscriber or self.is_metered

    @property
    def plan_label(self) -> str:
        if self.is_subscriber:
            return "Monthly Unlimited ($24.99/mo)"
        if self.is_metered:
            return "Pay per minute ($1.00/min)"
        return "No plan"


class Conversation(db.Model):
    __tablename__ = "conversations"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    companion_id = db.Column(db.String(50), nullable=False, index=True)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at = db.Column(db.DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)

    messages = db.relationship("Message", backref="conversation", cascade="all, delete-orphan",
                               order_by="Message.created_at")


class Message(db.Model):
    __tablename__ = "messages"

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey("conversations.id"), nullable=False, index=True)
    role = db.Column(db.String(20), nullable=False)  # 'user' | 'assistant'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)


class MinuteUsage(db.Model):
    """One row per (user, started-minute bucket). A 'started minute' is any
    UTC minute window in which the user sent at least one chat message."""
    __tablename__ = "minute_usage"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    minute_bucket = db.Column(db.BigInteger, nullable=False)  # int(epoch_seconds // 60)
    created_at = db.Column(db.DateTime(timezone=True), default=utcnow, nullable=False)
    stripe_reported = db.Column(db.Boolean, default=False, nullable=False)

    __table_args__ = (
        db.UniqueConstraint("user_id", "minute_bucket", name="uq_user_minute"),
    )
