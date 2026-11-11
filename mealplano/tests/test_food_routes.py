"""Milestone 7 tests: every food page through the Flask test client."""

import html
import time
import unittest

from mealplano.tests.test_routes import RouteCase


class FoodPageCase(RouteCase):
    def setUp(self):
        super().setUp()
        self.register()
        self.login()
        with self.client.session_transaction() as s:
            self.uid = s["user_id"]
        self.service = self.app.extensions["food_service"]

    def add(self, category, name, price):
        return self.post("/foods/add", {"category": category, "name": name, "price": price})

    def follow(self, response):
        """Load the page a POST redirected to (the flash message shows there)."""
        self.assertEqual(response.status_code, 302)
        return self.client.get(response.headers["Location"]).get_data(as_text=True)


class MenuAndChangeTests(FoodPageCase):
    def test_fr2_add_shows_in_price_position(self):
        self.follow(self.add("Lunch", "Adobo", "80"))
        page = self.follow(self.add("Lunch", "Tinola", "75"))
        self.assertIn("Added Tinola to Lunch at ₱75.00.", page)
        table = page[page.index("<tbody>"):]                     # skip the flash message above
        self.assertLess(table.index("Tinola"), table.index("Adobo"))   # cheaper first

    def test_fr2_duplicate_in_same_category_rejected(self):
        self.add("Lunch", "Adobo", "80")
        page = self.follow(self.add("Lunch", "adobo", "90"))
        self.assertIn("is already in Lunch", html.unescape(page))
        self.assertEqual(self.service.find(self.uid, "adobo"), [("Lunch", "Adobo", 8000)])

    def test_fr2_same_food_in_other_category_allowed(self):
        self.add("Lunch", "Adobo", "80")
        page = self.follow(self.add("Dinner", "adobo", "90"))
        self.assertIn("Added adobo to Dinner at ₱90.00.", page)
        self.assertEqual(self.service.find(self.uid, "Adobo"),
                         [("Lunch", "Adobo", 8000), ("Dinner", "adobo", 9000)])

    def test_delete_and_update_hit_only_the_row_clicked(self):
        self.add("Lunch", "Adobo", "80")
        self.add("Dinner", "Adobo", "90")
        self.follow(self.post("/foods/update", {"category": "Dinner", "name": "Adobo", "price": "95"}))
        page = self.follow(self.post("/foods/delete", {"category": "Lunch", "name": "Adobo"}))
        self.assertIn("Deleted Adobo (₱80.00) from Lunch.", page)
        self.assertEqual(self.service.find(self.uid, "Adobo"), [("Dinner", "Adobo", 9500)])

    def test_add_invalid_inputs_show_message_not_crash(self):
        cases = [("Lunch", "Adobo", "abc", "at most 2 decimal places"),
                 ("Lunch", "Adobo", "0", "from ₱0.01"),
                 ("Lunch", "Adobo", "-5", "at most 2 decimal places"),
                 ("Lunch", "", "80", "enter a food name"),
                 ("Lunch", "x" * 51, "80", "at most 50"),
                 ("Brunch", "Adobo", "80", "Breakfast, Lunch, Dinner, or Snacks")]
        for category, name, price, message in cases:
            with self.subTest(name=name[:10], price=price, category=category):
                page = self.follow(self.add(category, name, price))
                self.assertIn(message, page)
        self.assertEqual(sum(self.service.counts(self.uid).values()), 0)

    def test_fr8_update_price(self):
        self.add("Lunch", "Adobo", "80")
        page = self.follow(self.post("/foods/update", {"category": "Lunch", "name": "Adobo", "price": "85.50"}))
        self.assertIn("Adobo: ₱80.00 → ₱85.50.", page)
        page = self.follow(self.post("/foods/update", {"category": "Lunch", "name": "Adobo", "price": "abc"}))
        self.assertIn("New price must be a number", page)
        page = self.follow(self.post("/foods/update", {"category": "Lunch", "name": "Lechon", "price": "100"}))
        self.assertIn('"Lechon" is not in Lunch.', html.unescape(page))

    def test_fr4_delete_then_fr18_undo(self):
        self.add("Lunch", "Adobo", "80")
        page = self.follow(self.post("/foods/delete", {"category": "Lunch", "name": "Adobo"}))
        self.assertIn("Deleted Adobo (₱80.00) from Lunch.", page)
        self.assertEqual(self.service.find(self.uid, "Adobo"), [])
        page = self.follow(self.post("/undo", {"category": "Lunch"}))
        self.assertIn("Undid deleting Adobo; it is back in Lunch at ₱80.00.", page)
        self.assertEqual(self.service.find(self.uid, "Adobo"), [("Lunch", "Adobo", 8000)])

    def test_undo_messages_and_empty_stack(self):
        self.add("Snacks", "Turon", "20")
        self.post("/foods/update", {"category": "Snacks", "name": "Turon", "price": "25"})
        self.assertIn("Undid the price change; Turon is back to ₱20.00.",
                      self.follow(self.post("/undo", {})))
        self.assertIn("Undid adding Turon to Snacks.", self.follow(self.post("/undo", {})))
        self.assertIn("Nothing to undo.", self.follow(self.post("/undo", {})))

    def test_undo_button_disabled_when_nothing_to_undo(self):
        self.assertRegex(self.client.get("/menu").get_data(as_text=True),
                         r'<button type="submit" class="secondary" disabled')

    def test_names_are_html_escaped(self):
        self.add("Snacks", "<script>alert(1)</script>", "10")
        page = self.client.get("/menu?category=Snacks").get_data(as_text=True)
        self.assertNotIn("<script>alert(1)</script>", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)

    def test_unknown_category_falls_back(self):
        self.assertEqual(self.client.get("/menu?category=Brunch").status_code, 200)

    def test_menu_fast_with_500_foods_per_category(self):
        for category in ["Breakfast", "Lunch", "Dinner", "Snacks"]:
            for i in range(500):
                self.service.add_food(self.uid, category, f"{category} dish {i:03d}", 100 + i)
        for url in ["/menu?category=Lunch", "/sort?category=Breakfast&category=Lunch"
                    "&category=Dinner&category=Snacks&go=1", "/tree?category=Dinner",
                    "/budget?amount=500&category=Lunch&category=Snacks&go=1"]:
            with self.subTest(url=url):
                start = time.perf_counter()
                r = self.client.get(url)
                self.assertEqual(r.status_code, 200)
                self.assertLess(time.perf_counter() - start, 1.0)   # NFR: no noticeable delay


class ReadPageTests(FoodPageCase):
    def setUp(self):
        super().setUp()
        for category, name, price in [("Breakfast", "Tapsilog", "95"), ("Breakfast", "Arroz Caldo", "40"),
                                      ("Lunch", "Adobo", "80.50"), ("Lunch", "Sinigang", "75"),
                                      ("Lunch", "Tinola", "75"), ("Snacks", "Turon", "35.25")]:
            self.service.add_food(self.uid, category, name, int(float(price) * 100 + 0.5))

    def test_fr3_search(self):
        page = self.client.get("/search?q=  turon ").get_data(as_text=True)
        self.assertIn("Turon", page)
        self.assertIn("Snacks", page)
        self.assertIn("₱35.25", page)
        # Quote marks come back HTML-escaped (&#34;), so compare the decoded text.
        self.assertIn('"Halo-halo" was not found.',
                      html.unescape(self.client.get("/search?q=Halo-halo").get_data(as_text=True)))
        self.assertIn("Please enter a food name.", self.client.get("/search?q=").get_data(as_text=True))
        self.assertNotIn("not found", self.client.get("/search").get_data(as_text=True))

    def test_search_lists_every_category(self):
        self.service.add_food(self.uid, "Dinner", "Tapsilog", 11000)
        page = self.client.get("/search?q=tapsilog").get_data(as_text=True)
        self.assertIn("Found in 2 categories.", page)
        self.assertLess(page.index("Breakfast"), page.index("Dinner"))
        self.assertIn("₱95.00", page)
        self.assertIn("₱110.00", page)

    def test_fr6_total_exact(self):
        page = self.client.get("/total?food=Lunch|Adobo&food=Snacks|Turon&go=1").get_data(as_text=True)
        self.assertIn("₱115.75", page)                        # 80.50 + 35.25
        self.assertIn('value="Lunch|Adobo" checked', page)          # ticks are remembered

    def test_total_same_food_two_categories(self):
        self.service.add_food(self.uid, "Dinner", "Adobo", 9000)
        page = self.client.get("/total?food=Lunch|Adobo&food=Dinner|Adobo&go=1").get_data(as_text=True)
        self.assertIn("₱170.50", page)                        # 80.50 + 90.00
        page = html.unescape(self.client.get("/total?typed=adobo&go=1").get_data(as_text=True))
        self.assertIn("Adobo is in Lunch and Dinner, so it was not added. Tick the one you mean.", page)
        page = self.client.get("/total?food=Brunch|Adobo&food=nonsense&go=1").get_data(as_text=True)
        self.assertIn("Not on your menu: Adobo", page)              # forged values do not crash
        page = self.client.get("/total?typed=adobo, Lumpia&go=1").get_data(as_text=True)
        self.assertIn("Not on your menu: Lumpia", page)
        self.assertIn("₱80.50", page)
        page = self.client.get("/total?go=1").get_data(as_text=True)
        self.assertIn("Enter at least one food name.", page)

    def test_fr16_sort_ties_alphabetical(self):
        page = self.client.get("/sort?category=Lunch&go=1").get_data(as_text=True)
        order = [page.index(n) for n in ["Sinigang", "Tinola", "Adobo"]]
        self.assertEqual(order, sorted(order))                     # 75, 75 (alphabetical), 80.50
        page = self.client.get("/sort?go=1").get_data(as_text=True)
        self.assertIn("Choose at least one category.", page)

    def test_fr17_best_plan_within_budget(self):
        # Breakfast: Tapsilog 95, Arroz Caldo 40. Lunch: Adobo 80.50, Sinigang 75, Tinola 75.
        # The closest total to 200 without going over is 95 + 80.50 = 175.50.
        page = self.client.get("/budget?amount=200&category=Breakfast&category=Lunch&go=1").get_data(as_text=True)
        self.assertIn("Tapsilog", page)
        self.assertIn("Adobo", page)
        self.assertIn("₱175.50", page)
        self.assertIn("₱24.50</strong> left over", page)
        self.assertIn("cheapest possible plan costs ₱115.00", page)   # 40 + 75
        page = self.client.get("/budget?amount=175.50&category=Breakfast&category=Lunch&go=1").get_data(as_text=True)
        self.assertIn("Uses your budget exactly.", page)
        page = self.client.get("/budget?amount=100&category=Breakfast&category=Lunch&go=1").get_data(as_text=True)
        self.assertIn("₱15.00</strong> over your budget", page)        # cheapest 115 - 100

    def test_budget_errors(self):
        cases = [("/budget?amount=abc&category=Lunch&go=1", "Budget must be a number"),
                 ("/budget?amount=100&go=1", "Choose at least one category."),
                 ("/budget?amount=100&category=Dinner&go=1", "Dinner has no foods yet.")]
        for url, message in cases:
            with self.subTest(url=url):
                self.assertIn(message, self.client.get(url).get_data(as_text=True))

    def test_fr7_tree_view_orders(self):
        for order in ["inorder", "preorder", "postorder", "levelorder"]:
            with self.subTest(order=order):
                page = self.client.get(f"/tree?category=Lunch&order={order}").get_data(as_text=True)
                self.assertIn("AVL tree height <strong>2</strong>", page)
        page = self.client.get("/tree?category=Lunch&order=inorder").get_data(as_text=True)
        visit_list = page[page.index('<ol class="traversal">'):]
        positions = [visit_list.index(n) for n in ["Sinigang", "Tinola", "Adobo"]]   # 75, 75, 80.50
        self.assertEqual(positions, sorted(positions))
        self.assertEqual(self.client.get("/tree?order=sideways").status_code, 200)


class AccessControlTests(RouteCase):
    def test_fr14_every_food_page_needs_login(self):
        for url in ["/menu", "/search", "/total", "/sort", "/budget", "/tree"]:
            with self.subTest(url=url):
                r = self.client.get(url)
                self.assertEqual(r.status_code, 302)
                self.assertIn("/login", r.headers["Location"])
        for url in ["/foods/add", "/foods/delete", "/foods/update", "/undo"]:
            with self.subTest(url=url):
                r = self.post(url, {"name": "Adobo", "price": "80", "category": "Lunch"})
                self.assertEqual(r.status_code, 302)
                self.assertIn("/login", r.headers["Location"])


if __name__ == "__main__":
    unittest.main()
