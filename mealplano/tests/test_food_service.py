"""Milestone 6 tests: accounts in SQLite and the food service (FR-2 to FR-20 at service level)."""

import random
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from mealplano import auth, db
from mealplano.dsa import CATEGORIES
from mealplano.food_service import FoodService
from mealplano.tests.helpers import check_tree
from mealplano.validation import InputError


class DatabaseCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmp.name) / "test.db")
        db.init_db(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def assert_db_matches_trees(self, service, user_id):
        """The SQLite copy and the in-memory trees must hold exactly the same foods."""
        in_db = {(r["category"], r["display_name"], r["price_centavos"])
                 for r in db.load_foods(self.db_path, user_id)}
        state = service._state(user_id)
        in_trees = {(c, n.display_name, n.price)
                    for c in CATEGORIES for n in state.trees[c].inorder()}
        self.assertEqual(in_db, in_trees)
        for tree in state.trees.values():
            check_tree(tree)


class AuthTests(DatabaseCase):
    def test_register_and_login(self):
        uid = auth.register(self.db_path, "harold", "password123")
        self.assertEqual(auth.authenticate(self.db_path, "harold", "password123"), uid)

    def test_password_stored_only_as_salted_hash(self):
        auth.register(self.db_path, "harold", "password123")
        auth.register(self.db_path, "maria", "password123")       # same password
        # db.connect closes the file; `with sqlite3.connect(...)` only commits (BUG_LOG.md).
        with db.connect(self.db_path) as conn:
            hashes = [row["password_hash"] for row in conn.execute("SELECT password_hash FROM users")]
        for h in hashes:
            self.assertNotIn("password123", h)
        self.assertNotEqual(hashes[0], hashes[1])                   # different salts

    def test_duplicate_username_any_case(self):
        auth.register(self.db_path, "harold", "password123")
        with self.assertRaises(InputError):
            auth.register(self.db_path, "HAROLD", "otherpass99")

    def test_wrong_password_and_unknown_user_both_fail(self):
        auth.register(self.db_path, "harold", "password123")
        self.assertIsNone(auth.authenticate(self.db_path, "harold", "wrongpass1"))
        self.assertIsNone(auth.authenticate(self.db_path, "nobody", "password123"))
        self.assertIsNone(auth.authenticate(self.db_path, "", ""))

    def test_short_password_rejected(self):
        with self.assertRaises(InputError):
            auth.register(self.db_path, "harold", "1234567")

    def test_accounts_survive_restart(self):
        auth.register(self.db_path, "harold", "password123")
        db.init_db(self.db_path)                                    # "restart": schema re-run
        self.assertIsNotNone(auth.authenticate(self.db_path, "harold", "password123"))


class MigrationTests(unittest.TestCase):
    """Databases made before same-name-in-several-categories was allowed are upgraded in place."""

    OLD_SCHEMA = db.SCHEMA.replace("UNIQUE (user_id, category, key)", "UNIQUE (user_id, key)")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self._tmp.name) / "old.db")
        with db.connect(self.db_path) as conn:
            conn.executescript(self.OLD_SCHEMA)
            conn.execute("INSERT INTO users (id, username, password_hash, created_at) "
                         "VALUES (1, 'harold', 'x', '2026-11-07')")
            for i, (cat, name, price) in enumerate([("Lunch", "Tinola", 7500), ("Lunch", "Adobo", 8000),
                                                    ("Dinner", "Menudo", 8500)], start=10):
                conn.execute("INSERT INTO foods VALUES (?, 1, ?, ?, ?, ?)",
                             (i, cat, name.lower(), name, price))

    def tearDown(self):
        self._tmp.cleanup()

    def test_old_database_is_upgraded_keeping_rows_and_order(self):
        self.assertIn("UNIQUE (user_id, key)", self.OLD_SCHEMA)
        db.init_db(self.db_path)
        with db.connect(self.db_path) as conn:
            self.assertFalse(db._has_old_name_rule(conn))
            rows = [tuple(r) for r in conn.execute("SELECT id, category, display_name FROM foods ORDER BY id")]
        self.assertEqual(rows, [(10, "Lunch", "Tinola"), (11, "Lunch", "Adobo"), (12, "Dinner", "Menudo")])
        service = FoodService(self.db_path)
        service.add_food(1, "Dinner", "Adobo", 9000)                    # allowed now
        with self.assertRaises(sqlite3.IntegrityError):                 # the database still guards a category
            db.insert_food(self.db_path, 1, "Dinner", "adobo", "Adobo", 9100)
        db.init_db(self.db_path)                                        # running again changes nothing
        self.assertEqual(len(db.load_foods(self.db_path, 1)), 4)


class FoodServiceTests(DatabaseCase):
    def setUp(self):
        super().setUp()
        self.uid = auth.register(self.db_path, "harold", "password123")
        self.service = FoodService(self.db_path)
        self.service.load_user(self.uid)

    def test_fr2_duplicate_rejected_within_category(self):
        self.service.add_food(self.uid, "Lunch", "Adobo", 8000)
        self.assertEqual(self.service.menu(self.uid, "Lunch"), [("Adobo", 8000)])
        with self.assertRaises(InputError) as ctx:
            self.service.add_food(self.uid, "Lunch", "ADOBO", 9000)
        self.assertIn("already in Lunch", str(ctx.exception))
        self.assert_db_matches_trees(self.service, self.uid)

    def test_fr2_same_food_allowed_in_other_categories(self):
        self.service.add_food(self.uid, "Breakfast", "Tapsilog", 9500)
        self.service.add_food(self.uid, "Lunch", "tapsilog", 10000)       # different price
        self.service.add_food(self.uid, "Dinner", "Tapsilog", 11000)
        self.assertEqual(self.service.find(self.uid, "TAPSILOG"), [
            ("Breakfast", "Tapsilog", 9500),
            ("Lunch", "tapsilog", 10000),
            ("Dinner", "Tapsilog", 11000),
        ])
        self.assert_db_matches_trees(self.service, self.uid)

    def test_same_name_changes_touch_only_its_category(self):
        self.service.add_food(self.uid, "Lunch", "Adobo", 8000)
        self.service.add_food(self.uid, "Dinner", "Adobo", 9000)
        self.service.update_price(self.uid, "Dinner", "adobo", 9500)
        self.assertEqual(self.service.delete_food(self.uid, "Lunch", "Adobo"), ("Lunch", "Adobo", 8000))
        self.assertEqual(self.service.find(self.uid, "Adobo"), [("Dinner", "Adobo", 9500)])
        self.assert_db_matches_trees(self.service, self.uid)
        self.service.undo(self.uid)                                       # brings back Lunch only
        self.service.undo(self.uid)                                       # Dinner back to 9000
        self.assertEqual(self.service.find(self.uid, "Adobo"),
                         [("Lunch", "Adobo", 8000), ("Dinner", "Adobo", 9000)])
        self.assert_db_matches_trees(self.service, self.uid)

    def test_invalid_category_and_name(self):
        with self.assertRaises(InputError):
            self.service.add_food(self.uid, "Brunch", "Adobo", 8000)
        with self.assertRaises(InputError):
            self.service.add_food(self.uid, "Lunch", "   ", 8000)

    def test_fr3_find(self):
        self.service.add_food(self.uid, "Snacks", "Turon", 2000)
        self.assertEqual(self.service.find(self.uid, "TURON"), [("Snacks", "Turon", 2000)])
        self.assertEqual(self.service.find(self.uid, "Halo-halo"), [])

    def test_delete_and_update_written_to_db(self):
        for name, price in [("Menudo", 9000), ("Adobo", 8000), ("Tinola", 7500)]:
            self.service.add_food(self.uid, "Lunch", name, price)
        self.assertEqual(self.service.delete_food(self.uid, "Lunch", "menudo"), ("Lunch", "Menudo", 9000))
        self.assertEqual(self.service.update_price(self.uid, "Lunch", "Adobo", 8500),
                         ("Lunch", "Adobo", 8000, 8500))
        self.assert_db_matches_trees(self.service, self.uid)
        with self.assertRaises(InputError):
            self.service.delete_food(self.uid, "Lunch", "Menudo")
        with self.assertRaises(InputError):
            self.service.update_price(self.uid, "Lunch", "Menudo", 100)
        with self.assertRaises(InputError):
            self.service.delete_food(self.uid, "Dinner", "Adobo")          # wrong category
        with self.assertRaises(InputError):
            self.service.delete_food(self.uid, "Brunch", "Adobo")          # invalid category

    def test_fr18_undo_mirrored_in_db(self):
        self.service.add_food(self.uid, "Lunch", "Adobo", 8000)
        self.service.add_food(self.uid, "Lunch", "Tinola", 7500)
        self.service.update_price(self.uid, "Lunch", "Adobo", 8500)
        self.service.delete_food(self.uid, "Lunch", "Tinola")
        expected = ["add", "update", "delete", "delete"]            # inverses, newest first
        for action in expected:
            self.assertEqual(self.service.undo(self.uid)[0], action)
            self.assert_db_matches_trees(self.service, self.uid)
        self.assertIsNone(self.service.undo(self.uid))
        self.assertEqual(db.load_foods(self.db_path, self.uid), [])

    def test_failed_db_write_leaves_tree_unchanged(self):
        self.service.add_food(self.uid, "Lunch", "Adobo", 8000)
        with mock.patch.object(db, "insert_food", side_effect=sqlite3.OperationalError("disk full")):
            with self.assertRaises(sqlite3.OperationalError):
                self.service.add_food(self.uid, "Lunch", "Tinola", 7500)
        self.assertEqual(self.service.find(self.uid, "Tinola"), [])
        self.assertEqual(self.service.undo_count(self.uid), 1)      # only the Adobo add
        self.assert_db_matches_trees(self.service, self.uid)

    def test_fr20_foods_survive_restart(self):
        self.service.add_food(self.uid, "Breakfast", "Tapsilog", 9500)
        self.service.add_food(self.uid, "Lunch", "Adobo", 8000)
        self.service.add_food(self.uid, "Dinner", "Adobo", 9000)
        self.service.update_price(self.uid, "Lunch", "Adobo", 8550)
        restarted = FoodService(self.db_path)                       # empty cache, same file
        self.assertEqual(restarted.find(self.uid, "adobo"),
                         [("Lunch", "Adobo", 8550), ("Dinner", "Adobo", 9000)])
        self.assertEqual(restarted.menu(self.uid, "Breakfast"), [("Tapsilog", 9500)])
        self.assertEqual(restarted.undo_count(self.uid), 0)         # undo is per session

    def test_fr12_two_users_keep_separate_adobo(self):
        other = auth.register(self.db_path, "maria", "password123")
        self.service.add_food(self.uid, "Lunch", "Adobo", 8000)
        self.service.add_food(other, "Dinner", "Adobo", 12000)      # no clash across users
        self.assertEqual(self.service.find(self.uid, "Adobo"), [("Lunch", "Adobo", 8000)])
        self.assertEqual(self.service.find(other, "Adobo"), [("Dinner", "Adobo", 12000)])
        self.service.delete_food(other, "Dinner", "Adobo")
        self.assertEqual(self.service.find(self.uid, "Adobo"), [("Lunch", "Adobo", 8000)])
        self.assert_db_matches_trees(self.service, self.uid)
        self.assert_db_matches_trees(self.service, other)

    def test_logout_drops_cache_and_undo(self):
        self.service.add_food(self.uid, "Lunch", "Adobo", 8000)
        self.service.logout(self.uid)
        self.assertEqual(self.service.undo_count(self.uid), 0)
        self.assertIsNone(self.service.undo(self.uid))
        self.assertEqual(self.service.find(self.uid, "Adobo"), [("Lunch", "Adobo", 8000)])

    def test_fr6_meal_total_exact(self):
        self.service.add_food(self.uid, "Lunch", "Adobo", 8050)
        self.service.add_food(self.uid, "Snacks", "Turon", 3525)
        found, missing, ambiguous, total = self.service.meal_total(
            self.uid, typed=["adobo", "Turon", "Lumpia", ""])
        self.assertEqual(total, 11575)                              # P80.50 + P35.25 = P115.75
        self.assertEqual(missing, ["Lumpia"])
        self.assertEqual(ambiguous, [])
        self.assertEqual([f[1] for f in found], ["Adobo", "Turon"])

    def test_meal_total_with_same_name_in_two_categories(self):
        self.service.add_food(self.uid, "Lunch", "Adobo", 8000)
        self.service.add_food(self.uid, "Dinner", "Adobo", 9000)
        # Ticked boxes name the category exactly: both Adobos can be in one day.
        found, missing, ambiguous, total = self.service.meal_total(
            self.uid, picks=[("Lunch", "Adobo"), ("Dinner", "adobo"), ("Snacks", "Adobo")])
        self.assertEqual(total, 17000)
        self.assertEqual(missing, ["Adobo"])                        # not in Snacks
        # A typed name in two categories is not guessed.
        found, missing, ambiguous, total = self.service.meal_total(self.uid, typed=["adobo"])
        self.assertEqual((found, total), ([], 0))
        self.assertEqual(ambiguous, [("Adobo", ["Lunch", "Dinner"])])
        with self.assertRaises(InputError):
            self.service.meal_total(self.uid)

    def test_reads_traversal_sort_budget(self):
        for name, price in [("m", 500), ("f", 300), ("t", 300)]:
            self.service.add_food(self.uid, "Snacks", name, price)
        # Keys (500,m), (300,f), (300,t): inserting t makes a left-right case at m,
        # so the AVL tree rotates and t becomes the root.
        foods, height = self.service.traversal(self.uid, "Snacks", "preorder")
        self.assertEqual([f[0] for f in foods], ["t", "f", "m"])
        menu = self.service.menu(self.uid, "Snacks")
        self.assertEqual([f[0] for f in menu], ["f", "t", "m"])       # cheapest first, tie alphabetical
        self.assertEqual(height, 2)
        with self.assertRaises(InputError):
            self.service.traversal(self.uid, "Snacks", "sideways")
        self.assertEqual([r[1] for r in self.service.sort_by_price(self.uid, ["Snacks"])],
                         ["f", "t", "m"])
        self.assertEqual(self.service.budget(self.uid, ["Snacks"], 1000)["total"], 500)   # best <= 1000
        self.assertEqual(self.service.budget(self.uid, ["Snacks"], 400)["total"], 300)

    def test_random_operations_keep_db_and_trees_in_sync(self):
        rng = random.Random(42)
        for _ in range(400):
            name = f"food{rng.randint(0, 40)}"
            op = rng.choice(["add", "add", "delete", "update", "undo"])
            try:
                if op == "add":
                    self.service.add_food(self.uid, rng.choice(CATEGORIES), name,
                                          rng.randint(1, 50000))
                elif op == "delete":
                    self.service.delete_food(self.uid, rng.choice(CATEGORIES), name)
                elif op == "update":
                    self.service.update_price(self.uid, rng.choice(CATEGORIES), name,
                                              rng.randint(1, 50000))
                else:
                    self.service.undo(self.uid)
            except InputError:
                pass                                                # duplicate / missing: expected
        self.assert_db_matches_trees(self.service, self.uid)
        restarted = FoodService(self.db_path)
        self.assert_db_matches_trees(restarted, self.uid)


if __name__ == "__main__":
    unittest.main()
