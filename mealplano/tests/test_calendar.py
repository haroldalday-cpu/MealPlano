"""Tests for the meal calendar: the food service methods and the calendar pages."""

import html
import sqlite3
import unittest
from datetime import date, timedelta
from unittest import mock

from mealplano import auth, db
from mealplano.dsa import plan_within_budget
from mealplano.food_service import FoodService
from mealplano.tests.test_food_service import DatabaseCase
from mealplano.tests.test_food_routes import FoodPageCase
from mealplano.validation import InputError, parse_date, parse_month

TODAY = date.today()
MENU = [("Breakfast", "Taho", 2500), ("Breakfast", "Tapsilog", 9500),
        ("Lunch", "Adobo", 8050), ("Lunch", "Pancit Canton", 6500),
        ("Dinner", "Menudo", 8500), ("Dinner", "Sisig", 11000),
        ("Snacks", "Turon", 2000), ("Snacks", "Kwek-Kwek", 2500)]


class CalendarServiceTests(DatabaseCase):
    def setUp(self):
        super().setUp()
        self.uid = auth.register(self.db_path, "harold", "password123")
        self.service = FoodService(self.db_path)
        for category, name, price in MENU:
            self.service.add_food(self.uid, category, name, price)

    def assert_db_matches_calendar(self, service=None, user_id=None):
        service, user_id = service or self.service, user_id or self.uid
        in_db = {(r["plan_date"], r["category"], r["display_name"], r["price_centavos"])
                 for r in db.load_plans(self.db_path, user_id)}
        in_tree = {(n.day.isoformat(), c, name, price)
                   for n in service._state(user_id).calendar.inorder()
                   for c, (name, price) in n.meals.items()}
        self.assertEqual(in_db, in_tree)

    def test_plan_copies_price_and_menu_changes_do_not_alter_it(self):
        self.assertEqual(self.service.plan_meal(self.uid, TODAY, "Lunch", "adobo"),
                         ("Lunch", "Adobo", 8050))
        self.service.update_price(self.uid, "Lunch", "Adobo", 9900)
        self.assertEqual(self.service.day_view(self.uid, TODAY)["meals"]["Lunch"], ("Adobo", 8050))
        self.service.delete_food(self.uid, "Lunch", "Adobo")
        self.assertEqual(self.service.day_view(self.uid, TODAY)["meals"]["Lunch"], ("Adobo", 8050))
        self.assert_db_matches_calendar()

    def test_plan_replaces_the_category_and_unplan_removes_it(self):
        self.service.plan_meal(self.uid, TODAY, "Lunch", "Adobo")
        self.service.plan_meal(self.uid, TODAY, "Lunch", "Pancit Canton")
        self.service.plan_meal(self.uid, TODAY, "Snacks", "Turon")
        view = self.service.day_view(self.uid, TODAY)
        self.assertEqual(view["meals"], {"Lunch": ("Pancit Canton", 6500), "Snacks": ("Turon", 2000)})
        self.assertEqual(view["total"], 8500)
        self.assertEqual(self.service.unplan_meal(self.uid, TODAY, "Lunch"), ("Pancit Canton", 6500))
        with self.assertRaises(InputError):
            self.service.unplan_meal(self.uid, TODAY, "Lunch")
        self.assert_db_matches_calendar()

    def test_plan_unknown_food_or_category_rejected(self):
        with self.assertRaises(InputError):
            self.service.plan_meal(self.uid, TODAY, "Lunch", "Lechon")
        with self.assertRaises(InputError):
            self.service.plan_meal(self.uid, TODAY, "Brunch", "Adobo")
        self.assertEqual(len(self.service._state(self.uid).calendar), 0)

    def test_sqlite_first_failed_write_leaves_tree_untouched(self):
        with mock.patch.object(db, "upsert_plans", side_effect=sqlite3.OperationalError("disk full")):
            with self.assertRaises(sqlite3.OperationalError):
                self.service.plan_meal(self.uid, TODAY, "Lunch", "Adobo")
        self.assertIsNone(self.service._state(self.uid).calendar.get(TODAY))
        self.service.plan_meal(self.uid, TODAY, "Lunch", "Adobo")
        with mock.patch.object(db, "delete_plan", side_effect=sqlite3.OperationalError("disk full")):
            with self.assertRaises(sqlite3.OperationalError):
                self.service.unplan_meal(self.uid, TODAY, "Lunch")
        self.assertIsNotNone(self.service._state(self.uid).calendar.get(TODAY))

    def test_save_budget_plan_is_all_or_nothing(self):
        day = TODAY + timedelta(days=3)
        with self.assertRaises(InputError):
            self.service.save_budget_plan(self.uid, day, [("Lunch", "Adobo"), ("Dinner", "Lechon")])
        self.assertEqual(db.load_plans(self.db_path, self.uid), [])
        with self.assertRaises(InputError):
            self.service.save_budget_plan(self.uid, day, [("Lunch", "Adobo"), ("Lunch", "Pancit Canton")])
        with self.assertRaises(InputError):
            self.service.save_budget_plan(self.uid, day, [])
        meals = self.service.save_budget_plan(self.uid, day, [("Breakfast", "taho"), ("Lunch", "Adobo")])
        self.assertEqual(meals, [("Breakfast", "Taho", 2500), ("Lunch", "Adobo", 8050)])
        self.assert_db_matches_calendar()

    def test_autoplan_fills_only_empty_slots_with_best_plan(self):
        self.service.plan_meal(self.uid, TODAY, "Lunch", "Adobo")
        state = self.service._state(self.uid)
        expected = plan_within_budget(state.trees, ["Breakfast", "Dinner", "Snacks"], 15000)
        plan = self.service.autoplan_day(self.uid, TODAY, 15000)
        self.assertEqual(plan, expected)
        self.assertTrue(plan["fits"])
        meals = self.service.day_view(self.uid, TODAY)["meals"]
        self.assertEqual(meals["Lunch"], ("Adobo", 8050))       # the planned slot is kept
        self.assertEqual(len(meals), 4)
        with self.assertRaises(InputError):
            self.service.autoplan_day(self.uid, TODAY, 15000)   # nothing left to fill
        self.assert_db_matches_calendar()

    def test_autoplan_that_does_not_fit_saves_nothing(self):
        plan = self.service.autoplan_day(self.uid, TODAY, 1000)
        self.assertFalse(plan["fits"])
        self.assertIsNone(self.service._state(self.uid).calendar.get(TODAY))

    def test_autoplan_skips_categories_with_no_foods(self):
        for name in ("Turon", "Kwek-Kwek"):
            self.service.delete_food(self.uid, "Snacks", name)
        plan = self.service.autoplan_day(self.uid, TODAY, 50000)
        self.assertEqual([c for c, _, _ in plan["picks"]], ["Breakfast", "Lunch", "Dinner"])

    def test_month_view_totals_and_over_budget_flags(self):
        self.service.set_goals(self.uid, 10000, 15000, 20000)
        first = date(TODAY.year, TODAY.month, 1)
        self.service.plan_meal(self.uid, first, "Dinner", "Sisig")        # 110.00: over daily
        self.service.plan_meal(self.uid, first, "Snacks", "Turon")        # day total 130.00
        self.service.plan_meal(self.uid, first + timedelta(days=1), "Lunch", "Adobo")   # 80.50
        view = self.service.month_view(self.uid, first.year, first.month)
        self.assertEqual(view["total"], 13000 + 8050)
        self.assertEqual(view["planned_days"], 2)
        self.assertTrue(view["over"])                                     # 210.50 > 200
        cells = {c["date"]: c for w in view["weeks"] for c in w["days"]}
        self.assertTrue(cells[first]["over"])
        self.assertEqual(cells[first]["count"], 2)
        self.assertFalse(cells[first + timedelta(days=1)]["over"])
        week_totals = sum(w["total"] for w in view["weeks"])
        self.assertEqual(week_totals, 13000 + 8050)
        for week in view["weeks"]:
            self.assertEqual(len(week["days"]), 7)
            self.assertEqual(week["days"][0]["date"].weekday(), 6)       # weeks start on Sunday
            self.assertEqual(week["over"], week["total"] > 15000)

    def test_no_budgets_means_never_over(self):
        self.service.plan_meal(self.uid, TODAY, "Dinner", "Sisig")
        view = self.service.month_view(self.uid, TODAY.year, TODAY.month)
        self.assertFalse(view["over"])
        self.assertFalse(any(c["over"] for w in view["weeks"] for c in w["days"]))

    def test_calendar_and_goals_survive_logout_and_restart(self):
        self.service.plan_meal(self.uid, TODAY, "Lunch", "Adobo")
        self.service.set_goals(self.uid, 20000, None, 500000)
        self.service.logout(self.uid)
        fresh = FoodService(self.db_path)                                  # a server restart
        self.assertEqual(fresh.day_view(self.uid, TODAY)["meals"], {"Lunch": ("Adobo", 8050)})
        self.assertEqual(fresh.goals(self.uid), (20000, None, 500000))

    def test_each_user_sees_only_their_calendar(self):
        other = auth.register(self.db_path, "other", "password123")
        self.service.add_food(other, "Lunch", "Adobo", 9000)
        self.service.plan_meal(self.uid, TODAY, "Lunch", "Adobo")
        self.assertEqual(self.service.day_view(other, TODAY)["meals"], {})
        self.service.plan_meal(other, TODAY, "Lunch", "Adobo")
        self.assertEqual(self.service.day_view(self.uid, TODAY)["meals"]["Lunch"], ("Adobo", 8050))
        self.assertEqual(self.service.day_view(other, TODAY)["meals"]["Lunch"], ("Adobo", 9000))
        self.assert_db_matches_calendar(user_id=other)


class DateParsingTests(unittest.TestCase):
    def test_parse_date(self):
        today = date(2026, 11, 15)
        self.assertEqual(parse_date("2026-11-20", today), date(2026, 11, 20))
        self.assertEqual(parse_date(" 2028-02-29 ", today), date(2028, 2, 29))
        for bad in ("", None, "2026-02-30", "2026-13-01", "20-11-2026", "2026-1-5",
                    "2026-11-20x", "1999-01-01", "2030-01-01", "２０２６-11-20"):
            with self.subTest(bad=bad), self.assertRaises(InputError):
                parse_date(bad, today)

    def test_parse_month_falls_back_to_this_month(self):
        today = date(2026, 11, 15)
        self.assertEqual(parse_month("2027-02", today), (2027, 2))
        for bad in ("", None, "2026-13", "2026-00", "1990-01", "2040-01", "abc"):
            with self.subTest(bad=bad):
                self.assertEqual(parse_month(bad, today), (2026, 11))


class CalendarPageTests(FoodPageCase):
    def setUp(self):
        super().setUp()
        for category, name, price in MENU:
            self.service.add_food(self.uid, category, name, price)
        self.day = TODAY.isoformat()

    def test_pages_need_login(self):
        self.post("/logout", {})
        for url in ("/calendar", f"/calendar/day?date={self.day}"):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 302)
        r = self.post("/calendar/plan", {"date": self.day, "category": "Lunch", "name": "Adobo"})
        self.assertEqual(r.status_code, 302)
        self.assertIn("/login", r.headers["Location"])

    def test_posts_need_csrf(self):
        for url in ("/calendar/plan", "/calendar/unplan", "/calendar/autoplan",
                    "/calendar/goals", "/budget/save"):
            with self.subTest(url=url):
                r = self.client.post(url, data={"date": self.day, "category": "Lunch", "name": "Adobo"})
                self.assertEqual(r.status_code, 400)
        self.assertEqual(len(self.service._state(self.uid).calendar), 0)

    def test_plan_and_remove_through_the_day_page(self):
        page = self.follow(self.post("/calendar/plan", {"date": self.day, "category": "Lunch",
                                                        "name": "Adobo"}))
        self.assertIn("Planned Adobo (₱80.50) for Lunch", page)
        self.assertIn("Day total", page)
        page = self.follow(self.post("/calendar/unplan", {"date": self.day, "category": "Lunch"}))
        self.assertIn("Removed Adobo from Lunch", page)
        page = self.follow(self.post("/calendar/unplan", {"date": self.day, "category": "Lunch"}))
        self.assertIn("Nothing is planned for Lunch", page)

    def test_bad_dates_show_a_message_not_a_crash(self):
        for bad in ("2026-02-30", "garbage", "", "1990-01-01"):
            with self.subTest(bad=bad):
                r = self.client.get(f"/calendar/day?date={bad}")
                self.assertEqual(r.status_code, 302)
                page = self.client.get(r.headers["Location"]).get_data(as_text=True)
                self.assertIn("flash-error", page)
                page = self.follow(self.post("/calendar/plan", {"date": bad, "category": "Lunch",
                                                                "name": "Adobo"}))
                self.assertIn("flash-error", page)
        self.assertEqual(self.client.get("/calendar?month=nonsense").status_code, 200)

    def test_goals_and_over_budget_warning(self):
        page = self.follow(self.post("/calendar/goals", {"daily": "100", "weekly": "",
                                                         "monthly": "abc", "month": self.day[:7]}))
        self.assertIn("Monthly budget must be a number", page)
        page = self.follow(self.post("/calendar/goals", {"daily": "100", "weekly": "",
                                                         "monthly": "", "month": self.day[:7]}))
        self.assertIn("Saved your calendar budgets.", page)
        self.assertEqual(self.service.goals(self.uid), (10000, None, None))
        self.service.plan_meal(self.uid, TODAY, "Dinner", "Sisig")
        page = self.client.get("/calendar").get_data(as_text=True)
        self.assertIn("over the daily budget", page)
        page = self.client.get(f"/calendar/day?date={self.day}").get_data(as_text=True)
        self.assertIn("₱10.00 over your daily budget", page)

    def test_autoplan_through_the_page(self):
        page = self.follow(self.post("/calendar/autoplan", {"date": self.day, "amount": "200"}))
        self.assertIn("Planned", page)
        self.assertEqual(len(self.service.day_view(self.uid, TODAY)["meals"]), 4)
        tomorrow = (TODAY + timedelta(days=1)).isoformat()
        page = self.follow(self.post("/calendar/autoplan", {"date": tomorrow, "amount": "10"}))
        self.assertIn("Nothing fits in ₱10.00", page)
        page = self.follow(self.post("/calendar/autoplan", {"date": tomorrow, "amount": "x"}))
        self.assertIn("Budget must be a number", page)

    def test_budget_page_saves_plan_and_ignores_tampered_prices(self):
        page = self.client.get("/budget?amount=200&category=Breakfast&category=Lunch&go=1")
        self.assertIn("Save to calendar", page.get_data(as_text=True))
        target = (TODAY + timedelta(days=2)).isoformat()
        page = self.follow(self.post("/budget/save", {"date": target, "price": "1",
                                                      "pick": ["Breakfast|Tapsilog", "Lunch|Adobo|1"]}))
        # "Adobo|1" is not a food: the whole save is refused.
        self.assertIn('"Adobo|1" is not in Lunch.', html.unescape(page))
        page = self.follow(self.post("/budget/save", {"date": target, "price": "1",
                                                      "pick": ["Breakfast|Tapsilog", "Lunch|Adobo"]}))
        self.assertIn("Saved the plan (₱175.50)", page)
        meals = self.service.day_view(self.uid, date.fromisoformat(target))["meals"]
        self.assertEqual(meals, {"Breakfast": ("Tapsilog", 9500), "Lunch": ("Adobo", 8050)})

    def test_month_grid_renders_every_layout(self):
        """Months starting on each weekday, 28/29/30/31 days, 4 to 6 week rows."""
        months = [(TODAY.year + (TODAY.month - 1 + i) // 12, (TODAY.month - 1 + i) % 12 + 1)
                  for i in range(-11, 24)]
        if (2028, 2) not in months:
            months.append((2028, 2))
        seen_starts = set()
        for year, month in months:
            with self.subTest(month=f"{year}-{month:02d}"):
                r = self.client.get(f"/calendar?month={year:04d}-{month:02d}")
                self.assertEqual(r.status_code, 200)
                page = r.get_data(as_text=True)
                self.assertIn(date(year, month, 1).strftime("%B %Y"), page)
                seen_starts.add(date(year, month, 1).weekday())
        self.assertEqual(len(seen_starts), 7)

    def test_month_navigation_stops_at_the_window(self):
        page = self.client.get("/calendar").get_data(as_text=True)
        self.assertIn("Previous", page)
        self.assertIn("Next", page)
        far = TODAY + timedelta(days=720)
        page = self.client.get(f"/calendar?month={far:%Y-%m}").get_data(as_text=True)
        self.assertIn(far.strftime("%B %Y"), page)


if __name__ == "__main__":
    unittest.main()


class SeedDemoTests(unittest.TestCase):
    """The README's demo walkthrough relies on these exact numbers."""

    def test_seed_demo_twice_gives_the_same_menu_and_calendar(self):
        import contextlib
        import io
        import tempfile
        from pathlib import Path

        from mealplano import seed_demo
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "instance" / "mealplano.db"
            with mock.patch.object(seed_demo, "DB_PATH", path), \
                    contextlib.redirect_stdout(io.StringIO()):
                seed_demo.main()
                seed_demo.main()                                  # reset, not duplicate
            service = FoodService(str(path))
            uid = db.get_user_by_username(str(path), "demo")["id"]
            self.assertEqual(sum(service.counts(uid).values()), len(seed_demo.MENU))
            self.assertEqual(service.goals(uid), seed_demo.GOALS)
            totals = [service.day_view(uid, TODAY + timedelta(days=i))["total"] for i in range(10)]
            self.assertEqual(totals, [20000, 18500, 18550, 19500, 44000, 17000, 12000,
                                      20050, 19000, 20500])
            self.assertEqual(len(db.load_plans(str(path), uid)), 35)   # 40 slots, 5 left empty
