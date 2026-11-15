"""SQLite storage for accounts and a durable copy of each user's foods (PRD Section 7).

The trees are the working data structure; SQLite only keeps data across
restarts. Every query is parameterised (never string-formatted) and every
food query is scoped to one user_id (PRD Section 12).
"""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT UNIQUE NOT NULL COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS foods (
    id             INTEGER PRIMARY KEY,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category       TEXT NOT NULL CHECK (category IN ('Breakfast','Lunch','Dinner','Snacks')),
    key            TEXT NOT NULL,
    display_name   TEXT NOT NULL,
    price_centavos INTEGER NOT NULL CHECK (price_centavos > 0),
    UNIQUE (user_id, category, key)
);

-- Meal calendar: one food per category per day. The name and price are
-- copied when the meal is planned, so later menu changes do not alter it.
CREATE TABLE IF NOT EXISTS meal_plans (
    id             INTEGER PRIMARY KEY,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    plan_date      TEXT NOT NULL,            -- YYYY-MM-DD
    category       TEXT NOT NULL CHECK (category IN ('Breakfast','Lunch','Dinner','Snacks')),
    display_name   TEXT NOT NULL,
    price_centavos INTEGER NOT NULL CHECK (price_centavos > 0),
    UNIQUE (user_id, plan_date, category)
);

-- Calendar budgets; NULL means "no budget set" for that period.
CREATE TABLE IF NOT EXISTS budget_goals (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    daily   INTEGER CHECK (daily > 0),
    weekly  INTEGER CHECK (weekly > 0),
    monthly INTEGER CHECK (monthly > 0)
);
"""

# A name is unique per category, not per user, so "Adobo" can be in Lunch AND
# Dinner. Databases created before that change have UNIQUE (user_id, key);
# SQLite cannot drop a constraint, so the table is rebuilt once, keeping ids
# (and therefore insertion order) unchanged.
_MIGRATE_FOODS = """
BEGIN;
CREATE TABLE foods_new (
    id             INTEGER PRIMARY KEY,
    user_id        INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    category       TEXT NOT NULL CHECK (category IN ('Breakfast','Lunch','Dinner','Snacks')),
    key            TEXT NOT NULL,
    display_name   TEXT NOT NULL,
    price_centavos INTEGER NOT NULL CHECK (price_centavos > 0),
    UNIQUE (user_id, category, key)
);
INSERT INTO foods_new (id, user_id, category, key, display_name, price_centavos)
    SELECT id, user_id, category, key, display_name, price_centavos FROM foods;
DROP TABLE foods;
ALTER TABLE foods_new RENAME TO foods;
COMMIT;
"""


@contextmanager
def connect(db_path):
    """Open a connection, commit on success, roll back on error, always close."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path):
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        if _has_old_name_rule(conn):
            conn.executescript(_MIGRATE_FOODS)


def _has_old_name_rule(conn):
    """True if foods still has the old UNIQUE (user_id, key) constraint."""
    for index in conn.execute("PRAGMA index_list(foods)").fetchall():
        if index["unique"]:
            # PRAGMA cannot take ? parameters. The name comes from SQLite's own
            # index list (e.g. "sqlite_autoindex_foods_1"), never from user input.
            columns = [c["name"] for c in conn.execute(f"PRAGMA index_info('{index['name']}')")]
            if columns == ["user_id", "key"]:
                return True
    return False


# ---- users ----

def create_user(db_path, username, password_hash):
    """Insert a user and return the new id. Raises sqlite3.IntegrityError if the name is taken."""
    with connect(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO users (username, password_hash, created_at) VALUES (?, ?, ?)",
            (username, password_hash, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        return cur.lastrowid


def get_user_by_username(db_path, username):
    with connect(db_path) as conn:
        return conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()


def get_user_by_id(db_path, user_id):
    with connect(db_path) as conn:
        return conn.execute("SELECT id, username FROM users WHERE id = ?", (user_id,)).fetchone()


# ---- foods ----

def load_foods(db_path, user_id):
    """All of one user's foods in INSERTION order (ORDER BY id).

    Never ORDER BY price or key: sorted input turns a plain BST into a chain
    (PRD Section 7). The AVL tree would cope, but insertion order is the rule.
    """
    with connect(db_path) as conn:
        return conn.execute(
            "SELECT category, display_name, price_centavos FROM foods "
            "WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()


def insert_food(db_path, user_id, category, key, display_name, price):
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO foods (user_id, category, key, display_name, price_centavos) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, category, key, display_name, price),
        )


def delete_food(db_path, user_id, category, key):
    with connect(db_path) as conn:
        return conn.execute(
            "DELETE FROM foods WHERE user_id = ? AND category = ? AND key = ?",
            (user_id, category, key),
        ).rowcount


def update_food_price(db_path, user_id, category, key, price):
    with connect(db_path) as conn:
        return conn.execute(
            "UPDATE foods SET price_centavos = ? WHERE user_id = ? AND category = ? AND key = ?",
            (price, user_id, category, key),
        ).rowcount


# ---- meal calendar ----

def load_plans(db_path, user_id):
    """All of one user's planned meals in insertion order (ORDER BY id)."""
    with connect(db_path) as conn:
        return conn.execute(
            "SELECT plan_date, category, display_name, price_centavos FROM meal_plans "
            "WHERE user_id = ? ORDER BY id",
            (user_id,),
        ).fetchall()


def upsert_plans(db_path, user_id, plan_date, meals):
    """Plan several meals for one date in ONE transaction: all are saved or none.

    meals = [(category, display_name, price)]. A category already planned that
    day is replaced.
    """
    with connect(db_path) as conn:
        conn.executemany(
            "INSERT INTO meal_plans (user_id, plan_date, category, display_name, price_centavos) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT (user_id, plan_date, category) DO UPDATE SET "
            "display_name = excluded.display_name, price_centavos = excluded.price_centavos",
            [(user_id, plan_date, c, name, price) for c, name, price in meals],
        )


def delete_plan(db_path, user_id, plan_date, category):
    with connect(db_path) as conn:
        return conn.execute(
            "DELETE FROM meal_plans WHERE user_id = ? AND plan_date = ? AND category = ?",
            (user_id, plan_date, category),
        ).rowcount


def get_goals(db_path, user_id):
    """(daily, weekly, monthly) in centavos; None for a budget that is not set."""
    with connect(db_path) as conn:
        row = conn.execute(
            "SELECT daily, weekly, monthly FROM budget_goals WHERE user_id = ?", (user_id,)
        ).fetchone()
    return (row["daily"], row["weekly"], row["monthly"]) if row else (None, None, None)


def set_goals(db_path, user_id, daily, weekly, monthly):
    with connect(db_path) as conn:
        conn.execute(
            "INSERT INTO budget_goals (user_id, daily, weekly, monthly) VALUES (?, ?, ?, ?) "
            "ON CONFLICT (user_id) DO UPDATE SET "
            "daily = excluded.daily, weekly = excluded.weekly, monthly = excluded.monthly",
            (user_id, daily, weekly, monthly),
        )
