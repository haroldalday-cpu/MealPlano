"""Tests for the budget planner (FR-17): best plan within the budget."""

import random
import time
import unittest

from mealplano.dsa import (CATEGORIES, AVLTree, BudgetError, PriceAVLTree, cheapest_food,
                           exhaustive_best, plan_within_budget)


class BudgetPlannerTests(unittest.TestCase):
    tree_class = PriceAVLTree

    def setUp(self):
        self.trees = {c: self.tree_class() for c in CATEGORIES}
        menu = {
            "Breakfast": [("Tapsilog", 9500), ("Arroz Caldo", 4000), ("Champorado", 4500)],
            "Lunch": [("Adobo", 8000), ("Sinigang", 12000), ("Tinola", 7500)],
            "Dinner": [("Bistek", 9000), ("Menudo", 8500)],
            "Snacks": [("Turon", 2000), ("Banana Cue", 2000), ("Puto", 1500)],
        }
        for category, foods in menu.items():
            for name, price in foods:
                self.trees[category].insert(name, price)

    def test_best_plan_below_budget(self):
        result = plan_within_budget(self.trees, ["Breakfast", "Lunch", "Dinner"], 29000)
        self.assertEqual(result["picks"], [
            ("Breakfast", "Tapsilog", 9500),
            ("Lunch", "Adobo", 8000),
            ("Dinner", "Bistek", 9000),
        ])
        self.assertEqual(result["total"], 26500)        # no plan lands between 26,500 and 29,000
        self.assertTrue(result["fits"])
        self.assertEqual(result["remaining"], 2500)
        self.assertEqual(result["shortfall"], 0)
        self.assertEqual(result["cheapest_total"], 20000)

    def test_plan_uses_budget_exactly_when_possible(self):
        result = plan_within_budget(self.trees, ["Breakfast", "Lunch", "Dinner"], 30000)
        self.assertEqual([p[1] for p in result["picks"]], ["Tapsilog", "Sinigang", "Menudo"])
        self.assertEqual((result["total"], result["remaining"]), (30000, 0))

    def test_budget_equal_to_cheapest_plan(self):
        result = plan_within_budget(self.trees, list(CATEGORIES), 21500)
        self.assertTrue(result["fits"])
        self.assertEqual(result["total"], 21500)
        self.assertEqual([p[1] for p in result["picks"]], ["Arroz Caldo", "Tinola", "Menudo", "Puto"])

    def test_budget_too_small_shows_cheapest_plan_and_shortfall(self):
        result = plan_within_budget(self.trees, list(CATEGORIES), 10000)
        self.assertFalse(result["fits"])
        self.assertEqual(result["total"], 21500)
        self.assertEqual(result["shortfall"], 11500)
        self.assertEqual(result["remaining"], 0)

    def test_single_category(self):
        result = plan_within_budget(self.trees, ["Lunch"], 10000)
        self.assertEqual(result["picks"], [("Lunch", "Adobo", 8000)])   # largest price <= 100.00

    def test_picks_follow_the_chosen_category_order(self):
        result = plan_within_budget(self.trees, ["Snacks", "Breakfast"], 11000)
        self.assertEqual([p[0] for p in result["picks"]], ["Snacks", "Breakfast"])
        self.assertEqual(result["total"], 11000)                         # 1,500 + 9,500

    def test_price_tie_goes_to_alphabetically_first(self):
        tree = self.tree_class()
        tree.insert("Turon", 2000)
        tree.insert("Banana Cue", 2000)
        self.assertEqual(cheapest_food(tree), ("Banana Cue", 2000))

    def test_invalid_budgets(self):
        for bad in [0, -500, "abc", 12.5, None]:
            with self.subTest(budget=bad):
                with self.assertRaises(BudgetError):
                    plan_within_budget(self.trees, ["Lunch"], bad)

    def test_no_categories(self):
        with self.assertRaises(BudgetError):
            plan_within_budget(self.trees, [], 10000)

    def test_empty_category(self):
        self.trees["Snacks"] = self.tree_class()
        with self.assertRaises(BudgetError) as ctx:
            plan_within_budget(self.trees, ["Lunch", "Snacks"], 10000)
        self.assertIn("Snacks", str(ctx.exception))

    def test_fr17_matches_exhaustive_search_on_random_menus(self):
        # Meet in the middle must find the same best total as trying every plan.
        rng = random.Random(42)
        for trial in range(400):
            trees = {c: self.tree_class() for c in CATEGORIES}
            for c in CATEGORIES:
                for i in range(rng.randint(1, 7)):
                    trees[c].insert(f"{c}{i}", rng.choice([500, 1000, rng.randint(1, 20000)]))  # ties too
            chosen = rng.sample(CATEGORIES, rng.randint(1, 4))
            budget = rng.randint(1, 60000)
            result = plan_within_budget(trees, chosen, budget)
            best = exhaustive_best(trees, chosen, budget)
            if best is None:
                self.assertFalse(result["fits"], f"trial {trial}")
                continue
            self.assertTrue(result["fits"], f"trial {trial}")
            self.assertEqual(result["total"], best, f"trial {trial}")
            # The picks are real foods, one per chosen category, and add up to the total.
            self.assertEqual([p[0] for p in result["picks"]], chosen)
            for category, name, price in result["picks"]:
                self.assertEqual(trees[category].search(name).price, price)
            self.assertEqual(sum(p[2] for p in result["picks"]), result["total"])


class NameOrderedTreeBudgetTests(BudgetPlannerTests):
    """The planner must also work on trees that are not ordered by price."""
    tree_class = AVLTree


class BudgetSpeedTests(unittest.TestCase):
    def test_four_categories_of_200_foods_is_fast(self):
        # Trying every plan would be 200**4 = 1.6 billion plans.
        rng = random.Random(7)
        trees = {c: PriceAVLTree() for c in CATEGORIES}
        for c in CATEGORIES:
            for i in range(200):
                trees[c].insert(f"{c} dish {i}", rng.randint(2000, 30000))
        start = time.perf_counter()
        result = plan_within_budget(trees, list(CATEGORIES), 75_000)
        self.assertLess(time.perf_counter() - start, 2.0)
        self.assertTrue(result["fits"])
        self.assertLessEqual(result["total"], 75_000)


if __name__ == "__main__":
    unittest.main()
