"""MealPLANO Flask app: accounts, access control, and the food pages.

Run from the project folder:
    python -m flask --app mealplano.app run
then open http://127.0.0.1:5000

Account routes live here; food routes are in food_routes.py.
"""

import os
import secrets
from functools import wraps
from pathlib import Path

from flask import (Flask, abort, flash, g, redirect, render_template, request, session,
                   url_for)

from mealplano import auth, db
from mealplano.food_routes import register_food_routes
from mealplano.food_service import FoodService
from mealplano.validation import InputError, format_pesos


def _load_secret_key(instance_dir):
    """Secret key from MEALPLANO_SECRET_KEY, else a random one saved in instance/ (never in code)."""
    key = os.environ.get("MEALPLANO_SECRET_KEY")
    if key:
        return key
    path = Path(instance_dir) / "secret_key"
    if not path.exists():
        path.write_text(secrets.token_hex(32), encoding="utf-8")
    return path.read_text(encoding="utf-8").strip()


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    app.config.update(
        DATABASE=str(Path(app.instance_path) / "mealplano.db"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        MAX_CONTENT_LENGTH=64 * 1024,       # every MealPLANO form is tiny
        MAX_FORM_PARTS=200,
    )
    if test_config:
        app.config.update(test_config)
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = _load_secret_key(app.instance_path)

    db.init_db(app.config["DATABASE"])
    service = FoodService(app.config["DATABASE"])
    app.extensions["food_service"] = service
    app.jinja_env.filters["pesos"] = format_pesos

    # ---------- CSRF: every POST form carries a per-session token ----------

    def csrf_token():
        if "csrf" not in session:
            session["csrf"] = secrets.token_urlsafe(32)
        return session["csrf"]

    app.jinja_env.globals["csrf_token"] = csrf_token

    @app.before_request
    def check_csrf():
        if request.method == "POST":
            sent = request.form.get("csrf_token", "")
            expected = session.get("csrf", "")
            # Compare as bytes: compare_digest raises TypeError on non-ASCII str (BUG_LOG.md).
            if not sent or not secrets.compare_digest(sent.encode(), expected.encode()):
                abort(400, "Form expired. Please go back, reload the page, and try again.")

    # ---------- response hardening ----------

    @app.after_request
    def security_headers(response):
        h = response.headers
        h.setdefault("X-Content-Type-Options", "nosniff")
        h.setdefault("X-Frame-Options", "DENY")
        h.setdefault("Referrer-Policy", "same-origin")
        h.setdefault("Content-Security-Policy",
                     "default-src 'self'; img-src 'self' data:; form-action 'self'; "
                     "frame-ancestors 'none'; base-uri 'none'")
        if session.get("user_id") is not None:
            # A user's menu must not stay in the browser cache after logout.
            h["Cache-Control"] = "no-store"
        return response

    def error_page(code, title, default_message):
        def handler(err):
            message = getattr(err, "description", None) or default_message
            if code == 500:
                message = default_message          # never show internal details
            return render_template("error.html", code=code, title=title, message=message), code
        return handler

    for code, title, message in [
        (400, "Bad request", "Something in that request was not valid."),
        (404, "Page not found", "That page does not exist."),
        (405, "Not allowed", "That action is not allowed this way."),
        (413, "Too large", "That form was too large."),
        (500, "Server error", "Something went wrong on our side. Your data was not changed "
                              "unless the page said so."),
    ]:
        app.register_error_handler(code, error_page(code, title, message))

    # ---------- who is logged in (FR-12, FR-14) ----------

    @app.before_request
    def load_user():
        g.user = None
        user_id = session.get("user_id")
        if user_id is not None:
            row = db.get_user_by_id(app.config["DATABASE"], user_id)
            if row is None:                      # account no longer exists
                session.clear()
            else:
                g.user = row

    def login_required(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                flash("Please log in first.")
                return redirect(url_for("login", next=request.path))
            return view(*args, **kwargs)
        return wrapped

    # ---------- account routes ----------

    @app.route("/")
    def index():
        return redirect(url_for("menu" if g.user else "login"))

    @app.route("/register", methods=["GET", "POST"])
    def register():
        if g.user:
            return redirect(url_for("menu"))
        if request.method == "POST":
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            confirm = request.form.get("confirm", "")
            try:
                if password != confirm:
                    raise InputError("The two passwords do not match.")
                auth.register(app.config["DATABASE"], username, password)
            except InputError as err:
                flash(str(err))
                return render_template("register.html", username=username), 400
            flash("Account created. Please log in.")
            return redirect(url_for("login"))
        return render_template("register.html", username="")

    @app.route("/login", methods=["GET", "POST"])
    def login():
        if g.user:
            return redirect(url_for("menu"))
        if request.method == "POST":
            username = request.form.get("username", "")
            user_id = auth.authenticate(app.config["DATABASE"], username,
                                        request.form.get("password", ""))
            if user_id is None:
                flash(auth.LOGIN_ERROR)
                return render_template("login.html", username=username), 401
            session.clear()                          # new session on login
            session["user_id"] = user_id
            service.load_user(user_id)               # rebuild the four trees (FR-20)
            target = request.args.get("next", "")
            # Only follow local paths, never another site.
            if not target.startswith("/") or target.startswith("//"):
                target = url_for("menu")
            return redirect(target)
        return render_template("login.html", username="")

    @app.route("/logout", methods=["POST"])
    def logout():
        if g.user:
            service.logout(g.user["id"])             # drop trees and undo stack
        session.clear()
        flash("You have been logged out.")
        return redirect(url_for("login"))

    register_food_routes(app, service, login_required)
    return app


# `flask --app mealplano.app run` finds create_app() by itself.
if __name__ == "__main__":
    create_app().run(debug=False)
