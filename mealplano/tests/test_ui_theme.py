"""Tests for the cooking-game look: star rating, chef moods, one-time highlights,
and that the decorations still respect the Content-Security-Policy."""

import re
import unittest
from datetime import date

from mealplano.food_routes import chef_mood_for_plan, plan_stars
from mealplano.tests.test_food_routes import FoodPageCase
from mealplano.tests.test_routes import RouteCase


def plan(fits=True, remaining=0):
    return {"fits": fits, "remaining": remaining}


class StarRatingTests(unittest.TestCase):
    def test_plan_stars(self):
        cases = [(plan(remaining=0), 20000, 3),          # exact
                 (plan(remaining=400), 20000, 3),        # exactly 2% left
                 (plan(remaining=401), 20000, 2),        # just over 2%
                 (plan(remaining=2000), 20000, 2),       # exactly 10% left
                 (plan(remaining=2001), 20000, 1),       # just over 10%
                 (plan(remaining=15000), 20000, 1),      # far under
                 (plan(fits=False), 10000, 0),           # nothing fits
                 (None, None, 0)]                        # no plan asked for yet
        for p, budget, stars in cases:
            with self.subTest(plan=p, budget=budget):
                self.assertEqual(plan_stars(p, budget), stars)

    def test_chef_mood_for_plan(self):
        self.assertEqual(chef_mood_for_plan(3, plan()), "proud")
        self.assertEqual(chef_mood_for_plan(1, plan(remaining=5000)), "happy")
        self.assertEqual(chef_mood_for_plan(0, plan(fits=False)), "worried")
        self.assertEqual(chef_mood_for_plan(0, None), "happy")


def assert_csp_safe(test, page, url):
    """No inline style attributes, no inline scripts, decorative SVG hidden from screen readers."""
    test.assertNotIn("style=", page, f"{url} has an inline style attribute")
    for tag in re.findall(r"<script\b[^>]*>", page):
        test.assertIn("src=", tag, f"{url} has an inline <script>")
    for tag in re.findall(r'<svg\b[^>]*class="art\b[^"]*"[^>]*>', page):
        test.assertIn('aria-hidden="true"', tag, f"{url}: decorative svg not hidden")


class LoggedOutThemeTests(RouteCase):
    def test_pages_are_csp_safe_and_have_the_chef(self):
        for url, mood in (("/login", "happy"), ("/register", "happy"), ("/no-such-page", "dizzy")):
            with self.subTest(url=url):
                page = self.client.get(url).get_data(as_text=True)
                assert_csp_safe(self, page, url)
                self.assertIn(f'data-mood="{mood}"', page)
                self.assertIn("class=\"bubble\"", page)


class ThemedPageTests(FoodPageCase):
    def seed(self):
        for category, name, price in [("Breakfast", "Taho", "25"), ("Lunch", "Pancit Canton", "65"),
                                      ("Dinner", "Menudo", "85"), ("Snacks", "Kwek-Kwek", "25")]:
            self.add(category, name, price)
        self.client.get("/menu")                              # clear the one-time highlight

    def test_every_page_is_csp_safe(self):
        empty_pages = ["/menu", "/total", "/sort?go=1&category=Lunch", "/tree", "/budget"]
        for url in empty_pages:
            with self.subTest(url=url, menu="empty"):
                assert_csp_safe(self, self.client.get(url).get_data(as_text=True), url)
        self.seed()
        day = date.today().isoformat()
        self.post("/calendar/plan", {"date": day, "category": "Lunch", "name": "Pancit Canton"})
        full_pages = ["/menu?category=Lunch", "/search?q=taho", "/total?food=Lunch|Pancit+Canton&go=1",
                      "/sort?go=1&category=Lunch&category=Snacks", "/budget?amount=200&category=Breakfast&go=1",
                      "/budget?amount=10&category=Lunch&go=1", "/calendar", f"/calendar/day?date={day}",
                      "/tree?category=Lunch&order=preorder", "/missing"]
        for url in full_pages:
            with self.subTest(url=url):
                assert_csp_safe(self, self.client.get(url).get_data(as_text=True), url)

    def test_empty_menu_shows_the_chef(self):
        page = self.client.get("/menu?category=Dinner").get_data(as_text=True)
        self.assertIn("chef-says", page)
        self.assertIn("No foods in Dinner yet.", page)
        self.assertIn("icon-dinner", page)

    def test_budget_ticket_stamp_stars_and_mood(self):
        self.seed()
        page = self.client.get("/budget?amount=200&category=Breakfast&category=Lunch"
                               "&category=Dinner&category=Snacks&go=1").get_data(as_text=True)
        self.assertIn("EXACT!", page)                           # 25 + 65 + 85 + 25 = 200
        self.assertIn('aria-label="3 of 3 stars"', page)
        self.assertIn('data-mood="proud"', page)
        self.assertIn("Uses your budget exactly.", page)

        page = self.client.get("/budget?amount=150&category=Lunch&go=1").get_data(as_text=True)
        self.assertIn("FITS!", page)
        self.assertIn('aria-label="1 of 3 stars"', page)        # 65 of 150: far under
        self.assertIn('data-mood="happy"', page)

        page = self.client.get("/budget?amount=10&category=Lunch&go=1").get_data(as_text=True)
        self.assertIn(">OVER<", page)
        self.assertIn('aria-label="0 of 3 stars"', page)
        self.assertIn('data-mood="worried"', page)

    def test_calendar_day_mood_follows_daily_budget(self):
        self.seed()
        day = date.today()
        self.post("/calendar/goals", {"daily": "50", "weekly": "", "monthly": "", "month": f"{day:%Y-%m}"})
        self.post("/calendar/plan", {"date": day.isoformat(), "category": "Snacks", "name": "Kwek-Kwek"})
        page = self.client.get(f"/calendar/day?date={day.isoformat()}").get_data(as_text=True)
        self.assertIn('data-mood="happy"', page)
        self.post("/calendar/plan", {"date": day.isoformat(), "category": "Dinner", "name": "Menudo"})
        page = self.client.get(f"/calendar/day?date={day.isoformat()}").get_data(as_text=True)
        self.assertIn('data-mood="worried"', page)
        self.assertIn(">OVER<", page)
        self.assertIn('class="art flame"', self.client.get("/calendar").get_data(as_text=True))

    def test_new_food_is_highlighted_once(self):
        page = self.follow(self.add("Lunch", "Adobo", "80.50"))
        self.assertEqual(page.count('class="just-added"'), 1)
        self.assertIn("+₱80.50", page)
        page = self.client.get("/menu?category=Lunch").get_data(as_text=True)
        self.assertNotIn("just-added", page)                     # gone on reload

    def test_highlight_only_on_its_own_category(self):
        self.add("Lunch", "Adobo", "80")
        page = self.client.get("/menu?category=Dinner").get_data(as_text=True)
        self.assertNotIn("just-added", page)

    def test_price_change_and_undo_are_highlighted(self):
        self.add("Lunch", "Adobo", "80")
        self.client.get("/menu")
        page = self.follow(self.post("/foods/update", {"category": "Lunch", "name": "Adobo", "price": "85.50"}))
        self.assertEqual(page.count('class="just-updated"'), 1)
        self.assertIn("₱80.00 → ₱85.50", page[page.index("score-pop"):])
        self.post("/foods/delete", {"category": "Lunch", "name": "Adobo"})
        self.client.get("/menu")
        page = self.follow(self.post("/undo", {"category": "Lunch"}))
        self.assertEqual(page.count('class="just-added"'), 1)   # the deleted food came back


if __name__ == "__main__":
    unittest.main()
