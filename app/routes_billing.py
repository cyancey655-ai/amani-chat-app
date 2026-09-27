"""Pricing, Stripe Checkout, webhooks, billing dashboard."""
from datetime import datetime, timezone

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import limiter
from .models import MinuteUsage, User, db
from .stripe_service import (
    DemoModeError,
    construct_webhook_event,
    create_checkout_session,
    retrieve_checkout_session,
)

billing_bp = Blueprint("billing", __name__)


def _activate_from_metadata(user_id, plan, customer_id=None, subscription_id=None):
    user = User.query.get(int(user_id))
    if not user:
        return None
    user.plan = plan
    user.plan_status = "active"
    if customer_id:
        user.stripe_customer_id = customer_id
    if subscription_id:
        user.stripe_subscription_id = subscription_id
    db.session.commit()
    return user


@billing_bp.route("/pricing")
def pricing():
    return render_template("pricing.html")


@billing_bp.route("/billing")
@login_required
def dashboard():
    month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    minutes = (
        MinuteUsage.query.filter(
            MinuteUsage.user_id == current_user.id,
            MinuteUsage.created_at >= month_start,
        ).count()
    )
    return render_template(
        "billing.html",
        minutes_this_month=minutes,
        estimated=minutes * current_app.config["PRICE_PER_MINUTE_USD"],
    )


@billing_bp.route("/billing/checkout/<plan>", methods=["POST"])
@login_required
@limiter.limit("10 per minute")
def checkout(plan):
    """Start Stripe Checkout for 'monthly' or 'metered'. Demo mode: banner + local demo plan."""
    if plan not in ("monthly", "metered"):
        return redirect(url_for("billing.pricing"))
    if current_app.config["STRIPE_SECRET_KEY"] == "":
        # Demo mode — clearly labeled, never a real charge.
        current_user.demo_plan = plan
        db.session.commit()
        return redirect(url_for("billing.dashboard"))
    try:
        session = create_checkout_session(current_app.config, current_user, plan)
    except (DemoModeError, Exception) as exc:  # noqa: BLE001
        current_app.logger.error("Checkout creation failed: %s", exc)
        return render_template("pricing.html", error="Payment setup is incomplete. Please try again later."), 500
    return redirect(session.url, code=303)


@billing_bp.route("/billing/success")
@login_required
def success():
    """After Checkout: confirm the session server-side, then activate."""
    session_id = request.args.get("session_id")
    activated = False
    if session_id and current_app.config["STRIPE_SECRET_KEY"]:
        try:
            session = retrieve_checkout_session(current_app.config, session_id)
            if session.payment_status == "paid":
                meta = session.metadata or {}
                _activate_from_metadata(
                    meta.get("user_id", current_user.id),
                    meta.get("plan", "monthly"),
                    customer_id=session.customer,
                    subscription_id=session.subscription,
                )
                activated = True
        except Exception as exc:  # noqa: BLE001
            current_app.logger.error("Success confirmation failed: %s", exc)
    return render_template("checkout_success.html", activated=activated)


@billing_bp.route("/billing/cancel")
@login_required
def cancel():
    return render_template("checkout_cancel.html")


@billing_bp.route("/stripe/webhook", methods=["POST"])
def webhook():
    """Stripe webhook with signature verification. Never trust unsigned payloads."""
    payload = request.get_data()
    sig = request.headers.get("Stripe-Signature", "")
    try:
        event = construct_webhook_event(current_app.config, payload, sig)
    except DemoModeError:
        return jsonify({"error": "webhook not configured"}), 503
    except Exception:  # noqa: BLE001 — bad signature
        return jsonify({"error": "invalid signature"}), 400

    etype = event["type"]
    obj = event["data"]["object"]

    if etype == "checkout.session.completed":
        meta = obj.get("metadata", {})
        _activate_from_metadata(
            meta.get("user_id"),
            meta.get("plan", "monthly"),
            customer_id=obj.get("customer"),
            subscription_id=obj.get("subscription"),
        )
    elif etype == "customer.subscription.updated":
        sub = obj
        user = User.query.filter_by(stripe_subscription_id=sub["id"]).first()
        if user:
            status = sub.get("status")
            user.plan_status = "active" if status in ("active", "trialing") else status or "past_due"
            db.session.commit()
    elif etype == "customer.subscription.deleted":
        sub = obj
        user = User.query.filter_by(stripe_subscription_id=sub["id"]).first()
        if user:
            user.plan_status = "canceled"
            user.plan = "none"
            db.session.commit()
    elif etype == "invoice.payment_failed":
        customer_id = obj.get("customer")
        user = User.query.filter_by(stripe_customer_id=customer_id).first()
        if user:
            user.plan_status = "past_due"
            db.session.commit()

    return jsonify({"received": True})
