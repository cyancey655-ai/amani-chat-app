"""Chat: pick a model, converse, per-minute billing for non-subscribers."""
import time

from flask import Blueprint, current_app, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from . import limiter
from .ai import chat_reply
from .companions import COMPANIONS, get_companion
from .models import Conversation, Message, MinuteUsage, db
from .stripe_service import report_meter_event

chat_bp = Blueprint("chat", __name__)


def _bill_started_minute(user):
    """Record one started minute for a pay-per-minute user.

    Returns True if this message opened a NEW billable minute.
    A 'started minute' = any UTC minute window with >= 1 user message.
    """
    bucket = int(time.time() // 60)
    existing = MinuteUsage.query.filter_by(user_id=user.id, minute_bucket=bucket).first()
    if existing:
        return False
    usage = MinuteUsage(user_id=user.id, minute_bucket=bucket)
    db.session.add(usage)
    try:
        db.session.commit()
    except Exception:  # noqa: BLE001 — concurrent insert won the race; minute already counted
        db.session.rollback()
        return False

    # Report to Stripe's billing meter (real mode only).
    if current_app.config["STRIPE_SECRET_KEY"] and user.stripe_customer_id:
        try:
            report_meter_event(
                current_app.config,
                user.stripe_customer_id,
                idempotency_key=f"amani-{user.id}-{bucket}",
            )
            usage.stripe_reported = True
            db.session.commit()
        except Exception as exc:  # noqa: BLE001 — never break chat on billing errors
            current_app.logger.error("Stripe meter event failed: %s", exc)
    return True


@chat_bp.route("/chat")
@login_required
def choose():
    """Model lineup for logged-in users."""
    if not current_user.can_chat:
        return redirect(url_for("billing.pricing"))
    conversations = (
        Conversation.query.filter_by(user_id=current_user.id)
        .order_by(Conversation.updated_at.desc())
        .limit(7)
        .all()
    )
    return render_template("chat_choose.html", companions=COMPANIONS, conversations=conversations)


@chat_bp.route("/chat/<companion_id>")
@login_required
def room(companion_id):
    companion = get_companion(companion_id)
    if not companion:
        return redirect(url_for("chat.choose"))
    if not current_user.can_chat:
        return redirect(url_for("billing.pricing"))
    conv_id = request.args.get("c", type=int)
    conversation = None
    if conv_id:
        conversation = Conversation.query.filter_by(id=conv_id, user_id=current_user.id).first()
    return render_template("chat.html", companion=companion, conversation=conversation)


@chat_bp.route("/api/chat", methods=["POST"])
@login_required
@limiter.limit("30 per minute")
def api_chat():
    if not current_user.can_chat:
        return jsonify({"error": "no_plan", "message": "Pick a plan to keep chatting."}), 402

    data = request.get_json(force=True, silent=True) or {}
    companion_id = data.get("companion_id", "")
    text = (data.get("message") or "").strip()
    companion = get_companion(companion_id)
    if not companion:
        return jsonify({"error": "bad_companion"}), 400
    if not text:
        return jsonify({"error": "empty"}), 400
    if len(text) > 2000:
        return jsonify({"error": "too_long"}), 400

    conv_id = data.get("conversation_id")
    conversation = None
    if conv_id:
        conversation = Conversation.query.filter_by(id=conv_id, user_id=current_user.id).first()
    if not conversation:
        conversation = Conversation(user_id=current_user.id, companion_id=companion_id)
        db.session.add(conversation)
        db.session.commit()

    db.session.add(Message(conversation_id=conversation.id, role="user", content=text))

    # Started-minute billing for pay-per-minute users (subscribers skip this).
    billed_minute = False
    minutes_used = None
    if current_user.is_metered and not current_user.is_subscriber:
        billed_minute = _bill_started_minute(current_user)
        minutes_used = MinuteUsage.query.filter_by(user_id=current_user.id).count()

    history = [
        {"role": m.role, "content": m.content}
        for m in Message.query.filter_by(conversation_id=conversation.id)
        .order_by(Message.created_at)
        .all()[-30:]
    ]
    try:
        reply = chat_reply(companion_id, history, current_app.config)
    except Exception as exc:  # noqa: BLE001
        current_app.logger.error("AI reply failed: %s", exc)
        db.session.rollback()
        return jsonify({"error": "ai_error", "message": "She's speechless for a moment — try again."}), 502

    db.session.add(Message(conversation_id=conversation.id, role="assistant", content=reply))
    conversation.updated_at = db.func.now()
    db.session.commit()

    return jsonify(
        {
            "reply": reply,
            "conversation_id": conversation.id,
            "billed_minute": billed_minute,
            "minutes_used": minutes_used,
            "plan": "monthly" if current_user.is_subscriber else "metered",
            "ai_demo": current_app.config["OPENAI_API_KEY"] == "",
        }
    )


@chat_bp.route("/api/history/<int:conv_id>")
@login_required
def api_history(conv_id):
    conversation = Conversation.query.filter_by(id=conv_id, user_id=current_user.id).first()
    if not conversation:
        return jsonify({"error": "not_found"}), 404
    return jsonify(
        {
            "companion_id": conversation.companion_id,
            "messages": [{"role": m.role, "content": m.content} for m in conversation.messages],
        }
    )
