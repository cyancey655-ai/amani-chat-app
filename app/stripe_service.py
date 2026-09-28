"""Stripe integration: Checkout sessions, Billing Meter events, webhooks.

All secrets come from env via the Flask config. In demo mode (no secret key)
every function raises DemoModeError so routes can show the demo banner instead.
"""
import stripe


class DemoModeError(RuntimeError):
    pass


def _client(config):
    key = config["STRIPE_SECRET_KEY"]
    if not key:
        raise DemoModeError("Stripe is not configured (demo mode).")
    stripe.api_key = key
    # This Stripe account has Managed Payments enabled, which requires
    # API version 2025-03-31.basil or greater (the SDK default is older).
    stripe.api_version = "2025-03-31.basil"
    return stripe


def create_checkout_session(config, user, plan):
    """Create a Stripe Checkout Session for 'monthly' ($24.99/mo) or
    'metered' ($1.00 per started minute, pay-as-you-go metered subscription)."""
    _client(config)
    if plan == "monthly":
        price = config["STRIPE_PRICE_MONTHLY"]
    elif plan == "metered":
        price = config["STRIPE_PRICE_METERED"]
    else:
        raise ValueError("plan must be 'monthly' or 'metered'")
    if not price:
        raise DemoModeError(f"Stripe price id for plan '{plan}' is not configured.")

    base = config["APP_BASE_URL"]
    line_item = {"price": price}
    if plan == "monthly":
        # Metered prices must not specify a quantity (Stripe rejects it).
        line_item["quantity"] = 1
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer_email=user.email,
        line_items=[line_item],
        success_url=f"{base}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base}/billing/cancel",
        metadata={"user_id": str(user.id), "plan": plan},
        subscription_data={"metadata": {"user_id": str(user.id), "plan": plan}},
    )
    return session


def report_meter_event(config, stripe_customer_id, idempotency_key=None):
    """Report one started minute ($1.00) to the Stripe Billing Meter."""
    _client(config)
    event_name = config["STRIPE_METER_EVENT_NAME"]
    kwargs = {
        "event_name": event_name,
        "payload": {"stripe_customer_id": stripe_customer_id, "value": "1"},
    }
    if idempotency_key:
        kwargs["idempotency_key"] = idempotency_key
    return stripe.billing.MeterEvent.create(**kwargs)


def construct_webhook_event(config, payload, sig_header):
    """Verify the webhook signature. Raises on failure."""
    _client(config)
    secret = config["STRIPE_WEBHOOK_SECRET"]
    if not secret:
        raise DemoModeError("Stripe webhook secret is not configured.")
    return stripe.Webhook.construct_event(payload, sig_header, secret)


def retrieve_checkout_session(config, session_id):
    _client(config)
    return stripe.checkout.Session.retrieve(session_id)
