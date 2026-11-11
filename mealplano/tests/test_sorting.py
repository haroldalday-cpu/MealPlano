"""Milestone 3 tests: Merge Sort, Quick Sort, and sort by price (FR-16)."""

import random
import unittest

from mealplano.dsa import CATEGORIES, AVLTree, merge_sort, quick_sort, sort_by_price


class SharedSortTests:
    sort = None

    def run_sort(self, items, key=lambda x: x):
        return type(self).sort(items, key=key)

    def test_random_numbers(self):
        rng = random.Random(42)
        data = [rng.randint(1, 100000) for _ in range(5000)]
        self.assertEqual(self.run_sort(data), sorted(data))

    def test_empty_and_one(self):
        self.assertEqual(self.run_sort([]), [])
        self.assertEqual(self.run_sort([7]), [7])

    def test_all_equal(self):
        self.assertEqual(self.run_sort([5] * 500), [5] * 500)

    def test_already_sorted_and_reversed(self):
        data = list(range(2000))
        self.assertEqual(self.run_sort(data), data)
        self.assertEqual(self.run_sort(data[::-1]), data)

    def test_many_duplicates(self):
        rng = random.Random(1)
        data = [rng.randint(1, 5) for _ in range(2000)]
        self.assertEqual(self.run_sort(data), sorted(data))

    def test_does_not_change_input(self):
        data = [3, 1, 2]
        self.run_sort(data)
        self.assertEqual(data, [3, 1, 2])

    def test_key_function(self):
        rows = [("b", 30), ("a", 10), ("c", 20)]
        self.assertEqual(self.run_sort(rows, key=lambda r: r[1]),
                         [("a", 10), ("c", 20), ("b", 30)])


class MergeSortTests(SharedSortTests, unittest.TestCase):
    sort = staticmethod(merge_sort)

    def test_stable(self):
        rows = [("adobo", 100), ("bulalo", 50), ("champorado", 100), ("dinuguan", 50)]
        self.assertEqual(merge_sort(rows, key=lambda r: r[1]),
                         [("bulalo", 50), ("dinuguan", 50), ("adobo", 100), ("champorado", 100)])


class QuickSortTests(SharedSortTests, unittest.TestCase):
    sort = staticmethod(quick_sort)

    def test_sorted_input_10000_no_recursion_error(self):
        # Worst case for a last-element pivot: O(n^2) time, but recursion only
        # follows the smaller (empty) side, so the depth stays tiny.
        data = list(range(10000))
        self.assertEqual(quick_sort(data), data)


class SortByPriceTests(unittest.TestCase):
    def setUp(self):
        self.trees = {c: AVLTree() for c in CATEGORIES}
        for name, price in [("Tinola", 7500), ("Adobo", 8000), ("Sinigang", 7500), ("Bistek", 9000)]:
            self.trees["Lunch"].insert(name, price)
        for name, price in [("Tapsilog", 7500), ("Arroz Caldo", 4000)]:
            self.trees["Breakfast"].insert(name, price)

    def test_fr16_one_category_ties_stay_alphabetical(self):
        self.assertEqual(sort_by_price(self.trees, ["Lunch"]), [
            ("Lunch", "Sinigang", 7500),
            ("Lunch", "Tinola", 7500),
            ("Lunch", "Adobo", 8000),
            ("Lunch", "Bistek", 9000),
        ])

    def test_fr16_all_categories(self):
        result = sort_by_price(self.trees, list(CATEGORIES))
        self.assertEqual([r[1] for r in result],
                         ["Arroz Caldo", "Sinigang", "Tapsilog", "Tinola", "Adobo", "Bistek"])
        prices = [r[2] for r in result]
        self.assertEqual(prices, sorted(prices))      # non-decreasing price

    def test_empty_category(self):
        self.assertEqual(sort_by_price(self.trees, ["Snacks"]), [])


if __name__ == "__main__":
    unittest.main()
