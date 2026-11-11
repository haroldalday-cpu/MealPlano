"""Milestone 4 tests: list-based searches used in the lookup benchmark."""

import random
import unittest

from mealplano.dsa.searching import binary_search, linear_search, sorted_insert


class SearchingTests(unittest.TestCase):
    def test_linear_search(self):
        items = [("tinola", 7500), ("adobo", 8000)]
        self.assertEqual(linear_search(items, "adobo"), 8000)
        self.assertIsNone(linear_search(items, "menudo"))
        self.assertIsNone(linear_search([], "adobo"))

    def test_binary_search_first_last_middle_missing(self):
        items = [(k, i) for i, k in enumerate("bdfhjln")]
        for i, k in enumerate("bdfhjln"):
            self.assertEqual(binary_search(items, k), i)
        for k in "acegikmo":                      # before, between and after every key
            self.assertIsNone(binary_search(items, k))
        self.assertIsNone(binary_search([], "a"))

    def test_sorted_insert_keeps_order_and_rejects_duplicates(self):
        rng = random.Random(42)
        items, model = [], {}
        for _ in range(2000):
            key = f"f{rng.randint(0, 800)}"
            price = rng.randint(1, 1000)
            self.assertEqual(sorted_insert(items, key, price), key not in model)
            model.setdefault(key, price)
        self.assertEqual(items, sorted(model.items()))
        for key, price in model.items():
            self.assertEqual(binary_search(items, key), price)


if __name__ == "__main__":
    unittest.main()
