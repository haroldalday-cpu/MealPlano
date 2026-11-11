"""Milestone 6 tests: account pages, sessions and access control through the Flask test client."""

import tempfile
import unittest
from pathlib import Path

from mealplano.app import create_app


class RouteCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.config = {"TESTING": True, "SECRET_KEY": "test-key",
                       "DATABASE": str(Path(self._tmp.name) / "test.db")}
        self.app = create_app(self.config)
        self.client = self.app.test_client()

    def tearDown(self):
        self._tmp.cleanup()

    def post(self, url, data, client=None):
        """POST with the session's CSRF token, like a real form."""
        client = client or self.client
        with client.session_transaction() as s:
            s.setdefault("csrf", "token-for-tests")
            token = s["csrf"]
        return client.post(url, data={**data, "csrf_token": token})

    def register(self, username="harold", password="password123", confirm=None):
        return self.post("/register", {"username": username, "password": password,
                                       "confirm": password if confirm is None else confirm})

    def login(self, username="harold", password="password123", client=None):
        return self.post("/login", {"username": username, "password": password}, client)


class AccountRouteTests(RouteCase):
    def test_register_then_login_then_logout(self):
        r = self.register()
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/login"))
        r = self.login()
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/menu"))
        page = self.client.get("/menu").data
        self.assertIn(b"harold", page)
        self.assertIn(b"Add a food", page)
        self.post("/logout", {})
        r = self.client.get("/menu")
        self.assertEqual(r.status_code, 302)                        # logged out again

    def test_register_errors(self):
        self.register()
        cases = [("HAROLD", "password123", None, b"already taken"),
                 ("newuser", "1234567", None, b"at least 8"),
                 ("newuser", "password123", "password124", b"do not match"),
                 ("a", "password123", None, b"3 to 30")]
        for username, password, confirm, message in cases:
            with self.subTest(username=username, password=password):
                r = self.register(username, password, confirm)
                self.assertEqual(r.status_code, 400)
                self.assertIn(message, r.data)

    def test_login_error_is_generic(self):
        self.register()
        wrong_password = self.login("harold", "wrongpass1")
        no_such_user = self.login("nobody", "password123")
        for r in (wrong_password, no_such_user):
            self.assertEqual(r.status_code, 401)
            self.assertIn(b"Invalid username or password.", r.data)
            self.assertNotIn(b"already taken", r.data)

    def test_fr14_food_pages_need_login(self):
        r = self.client.get("/menu")
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login?next=/menu", r.headers["Location"])
        self.assertTrue(self.client.get("/").headers["Location"].endswith("/login"))

    def test_login_follows_local_next_only(self):
        self.register()
        with self.client.session_transaction() as s:
            s["csrf"] = "t"
        r = self.client.post("/login?next=//evil.example/steal",
                             data={"username": "harold", "password": "password123",
                                   "csrf_token": "t"})
        self.assertTrue(r.headers["Location"].endswith("/menu"))

    def test_post_without_csrf_token_is_rejected(self):
        r = self.client.post("/register", data={"username": "harold", "password": "password123",
                                                "confirm": "password123"})
        self.assertEqual(r.status_code, 400)
        r = self.client.post("/register", data={"username": "harold", "password": "password123",
                                                "confirm": "password123", "csrf_token": "forged"})
        self.assertEqual(r.status_code, 400)

    def test_logout_requires_post(self):
        self.assertEqual(self.client.get("/logout").status_code, 405)

    def test_fr20_foods_survive_server_restart(self):
        self.register()
        self.login()
        with self.client.session_transaction() as s:
            uid = s["user_id"]
        self.app.extensions["food_service"].add_food(uid, "Lunch", "Adobo", 8000)

        restarted = create_app(self.config)                         # new app, same database file
        client = restarted.test_client()
        self.login(client=client)
        page = client.get("/menu?category=Lunch").data
        self.assertIn(b"Adobo", page)
        self.assertEqual(restarted.extensions["food_service"].find(uid, "adobo"),
                         [("Lunch", "Adobo", 8000)])

    def test_fr12_users_see_only_their_own_foods(self):
        self.register("harold")
        self.register("maria")
        service = self.app.extensions["food_service"]
        maria_client = self.app.test_client()
        self.login("maria", client=maria_client)
        with maria_client.session_transaction() as s:
            maria_id = s["user_id"]
        service.add_food(maria_id, "Dinner", "Bistek", 9000)

        self.login("harold")
        self.assertNotIn(b"Bistek", self.client.get("/menu?category=Dinner").data)
        self.assertIn(b"was not found", self.client.get("/search?q=Bistek").data)
        self.assertIn(b"Bistek", maria_client.get("/menu?category=Dinner").data)


if __name__ == "__main__":
    unittest.main()
