"""Milestone 8 tests: input edge cases, injection attempts, error pages, and response hardening."""

import html
import unittest
from unittest import mock

from mealplano import db
from mealplano.tests.test_food_routes import FoodPageCase
from mealplano.tests.test_routes import RouteCase
from mealplano.validation import InputError, clean_name


class NameRuleTests(unittest.TestCase):
    def test_inner_spaces_collapse(self):
        self.assertEqual(clean_name("  Pancit \t  Canton \n"), "Pancit Canton")

    def test_control_characters_rejected(self):
        for bad in ["Ado\x00bo", "Ado\x1bbo", "Adobo​"]:      # NUL, ESC, zero-width space
            with self.subTest(name=repr(bad)):
                with self.assertRaises(InputError):
                    clean_name(bad)

    def test_unicode_letters_allowed(self):
        self.assertEqual(clean_name("Café Ñilaga"), "Café Ñilaga")


class InputEdgeCaseTests(FoodPageCase):
    def test_spacing_variants_are_one_food(self):
        self.add("Lunch", "Pancit Canton", "65")
        page = self.follow(self.add("Lunch", "pancit    canton", "70"))
        self.assertIn("is already in Lunch", html.unescape(page))
        self.assertEqual(self.service.find(self.uid, " PANCIT  CANTON "),
                         [("Lunch", "Pancit Canton", 6500)])

    def test_sql_injection_text_is_stored_as_plain_text(self):
        nasty = "'; DROP TABLE foods; --"
        self.follow(self.add("Snacks", nasty, "10"))
        self.follow(self.add("Snacks", "Robert'); DELETE FROM users;--", "10"))
        self.assertEqual(self.service.find(self.uid, nasty), [("Snacks", nasty, 1000)])
        with db.connect(self.config["DATABASE"]) as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM foods").fetchone()[0], 2)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0], 1)
        page = self.client.get("/search?q=" + nasty).get_data(as_text=True)
        self.assertIn("Snacks", page)

    def test_unicode_names_and_case_insensitive_search(self):
        self.follow(self.add("Breakfast", "Café con Leche", "55"))
        self.assertEqual(self.service.find(self.uid, "CAFÉ CON LECHE")[0][1], "Café con Leche")
        page = self.client.get("/menu?category=Breakfast").get_data(as_text=True)
        self.assertIn("Café con Leche", page)

    def test_meal_total_item_cap(self):
        many = "&".join(f"food=Lunch|x{i}" for i in range(201))
        page = self.client.get(f"/total?{many}&go=1").get_data(as_text=True)
        self.assertIn("Choose at most 200 foods", page)

    def test_huge_price_and_long_inputs_do_not_crash(self):
        page = self.follow(self.add("Lunch", "Adobo", "9" * 5000))
        self.assertIn("from ₱0.01 to ₱100,000.00", page)
        r = self.client.get("/search?q=" + "a" * 5000)
        self.assertEqual(r.status_code, 200)
        self.assertIn("at most 50", r.get_data(as_text=True))


class CoverageGapTests(FoodPageCase):
    """Paths the coverage report showed no test had run."""

    def test_delete_missing_food_via_route(self):
        page = self.follow(self.post("/foods/delete", {"category": "Dinner", "name": "Lechon"}))
        self.assertIn('"Lechon" is not in Dinner.', html.unescape(page))
        page = self.follow(self.post("/foods/delete", {"name": "Lechon"}))   # no category sent
        self.assertIn("Please choose Breakfast, Lunch, Dinner, or Snacks.", page)

    def test_logged_in_user_skips_login_and_register(self):
        for url in ["/login", "/register"]:
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertEqual(r.status_code, 302)
                self.assertTrue(r.headers["Location"].endswith("/menu"))

    def test_bst_height_counts_left_branches(self):
        from mealplano.dsa import BST
        tree = BST()
        for key in ["m", "f", "c", "a", "t"]:      # left chain m-f-c-a, plus t on the right
            tree.insert(key, 100)
        self.assertEqual(tree.height(), 4)


class ErrorPageAndHeaderTests(RouteCase):
    def test_register_page_renders(self):
        r = self.client.get("/register")
        self.assertEqual(r.status_code, 200)
        self.assertIn(b"Create an account", r.data)

    def test_non_ascii_csrf_token_rejected_not_crash(self):
        with self.client.session_transaction() as s:
            s["csrf"] = "token"
        r = self.client.post("/register", data={"username": "harold", "password": "password123",
                                                "confirm": "password123", "csrf_token": "ñ"})
        self.assertEqual(r.status_code, 400)
        self.assertIn(b"Form expired", r.data)

    def test_friendly_404_and_405(self):
        r = self.client.get("/no-such-page")
        self.assertEqual(r.status_code, 404)
        self.assertIn(b"Page not found", r.data)
        r = self.client.get("/foods/add")
        self.assertEqual(r.status_code, 405)
        self.assertIn(b"Not allowed", r.data)

    def test_oversized_form_rejected(self):
        with self.client.session_transaction() as s:
            s["csrf"] = "t"
        r = self.client.post("/login", data={"username": "x" * 70_000, "password": "p",
                                             "csrf_token": "t"})
        self.assertEqual(r.status_code, 413)

    def test_500_page_hides_internal_details(self):
        self.app.config["PROPAGATE_EXCEPTIONS"] = False
        self.register()
        self.login()
        service = self.app.extensions["food_service"]
        with mock.patch.object(service, "menu", side_effect=RuntimeError("secret internal detail")):
            r = self.client.get("/menu")
        self.assertEqual(r.status_code, 500)
        self.assertIn(b"Something went wrong", r.data)
        self.assertNotIn(b"secret internal detail", r.data)
        self.assertNotIn(b"Traceback", r.data)

    def test_security_headers(self):
        r = self.client.get("/login")
        self.assertEqual(r.headers["X-Frame-Options"], "DENY")
        self.assertEqual(r.headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("frame-ancestors 'none'", r.headers["Content-Security-Policy"])
        self.assertNotIn("no-store", r.headers.get("Cache-Control", ""))

    def test_logged_in_pages_not_cached(self):
        self.register()
        self.login()
        self.assertEqual(self.client.get("/menu").headers["Cache-Control"], "no-store")

    def test_deleted_account_session_is_dropped(self):
        self.register()
        self.login()
        with db.connect(self.config["DATABASE"]) as conn:
            conn.execute("DELETE FROM users")
        r = self.client.get("/menu")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.headers["Location"])


if __name__ == "__main__":
    unittest.main()
