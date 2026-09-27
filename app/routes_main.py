"""Landing page, terms, privacy."""
from flask import Blueprint, render_template

from .companions import COMPANIONS

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html", companions=COMPANIONS)


@main_bp.route("/terms")
def terms():
    return render_template("terms.html")


@main_bp.route("/privacy")
def privacy():
    return render_template("privacy.html")


@main_bp.app_errorhandler(404)
def not_found(_e):
    return render_template("404.html"), 404
