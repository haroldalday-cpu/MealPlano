"""Registration and login (FR-9 to FR-11).

Passwords are stored only as salted hashes from werkzeug.security
(scrypt by default; the salt is random per password and stored inside the hash).
"""

import sqlite3

from werkzeug.security import check_password_hash, generate_password_hash

from mealplano import db
from mealplano.validation import InputError, check_password, check_username

LOGIN_ERROR = "Invalid username or password."      # generic on purpose (FR-9 to FR-14)

# Checked against when the username does not exist, so a wrong username takes
# about as long as a wrong password and timing does not reveal which names exist.
_DUMMY_HASH = generate_password_hash("not-a-real-password")


def register(db_path, username, password):
    """Create an account and return its user id. Raises InputError with a user-safe message."""
    username = check_username(username)
    password = check_password(password)
    try:
        return db.create_user(db_path, username, generate_password_hash(password))
    except sqlite3.IntegrityError:
        raise InputError("That username is already taken.") from None


def authenticate(db_path, username, password):
    """Return the user id if the username and password match, else None."""
    row = db.get_user_by_username(db_path, (username or "").strip())
    if row is None:
        check_password_hash(_DUMMY_HASH, password or "")
        return None
    if check_password_hash(row["password_hash"], password or ""):
        return row["id"]
    return None
