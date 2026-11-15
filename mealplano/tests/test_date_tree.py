"""Tests for the meal calendar's date tree: AVL keyed by date, with a range query."""

import random
import unittest
from datetime import date, timedelta

from mealplano.dsa import DateAVLTree


def check_date_tree(tree):
    """In-order dates strictly increase, the size matches, heights are right, balance is -1..1."""
    days = tree.inorder()
    keys = [n.key for n in days]
    assert keys == sorted(set(keys)), "in-order dates not strictly increasing"
    assert len(days) == len(tree), f"size {len(tree)} but {len(days)} nodes"
    assert all(n.meals for n in days), "a day with no meals was left in the tree"

    def walk(node):
        if node is None:
            return 0
        left, right = walk(node.left), walk(node.right)
        assert node.height == 1 + max(left, right), f"{node.day} has a wrong height"
        assert abs(left - right) <= 1, f"{node.day} has balance factor {left - right}"
        return 1 + max(left, right)

    walk(tree.root)


D = date(2026, 11, 1)


class DateTreeBasics(unittest.TestCase):
    def test_empty_tree(self):
        tree = DateAVLTree()
        self.assertEqual(len(tree), 0)
        self.assertIsNone(tree.get(D))
        self.assertEqual(tree.day_total(D), 0)
        self.assertEqual(tree.range(D, D + timedelta(days=30)), [])
        self.assertIsNone(tree.remove_meal(D, "Lunch"))
        self.assertEqual(tree.inorder(), [])

    def test_set_replace_and_remove_meals(self):
        tree = DateAVLTree()
        self.assertIsNone(tree.set_meal(D, "Lunch", "Adobo", 8000))
        self.assertIsNone(tree.set_meal(D, "Snacks", "Turon", 2000))
        self.assertEqual(len(tree), 1)                          # one day, two meals
        self.assertEqual(tree.day_total(D), 10000)
        self.assertEqual(tree.set_meal(D, "Lunch", "Tinola", 7500), ("Adobo", 8000))
        self.assertEqual(tree.get(D).meals["Lunch"], ("Tinola", 7500))
        self.assertEqual(tree.remove_meal(D, "Lunch"), ("Tinola", 7500))
        self.assertEqual(len(tree), 1)
        self.assertIsNone(tree.remove_meal(D, "Lunch"))         # already gone
        self.assertEqual(tree.remove_meal(D, "Snacks"), ("Turon", 2000))
        self.assertEqual(len(tree), 0)                          # last meal removes the day
        self.assertIsNone(tree.get(D))

    def test_range_bounds_are_inclusive(self):
        tree = DateAVLTree()
        for offset in range(10):
            tree.set_meal(D + timedelta(days=offset), "Lunch", f"Food {offset}", 100 * (offset + 1))
        days = tree.range(D + timedelta(days=2), D + timedelta(days=4))
        self.assertEqual([n.day for n in days], [D + timedelta(days=i) for i in (2, 3, 4)])
        self.assertEqual(tree.range_total(D + timedelta(days=2), D + timedelta(days=4)), 300 + 400 + 500)
        self.assertEqual(tree.range(D + timedelta(days=5), D + timedelta(days=4)), [])   # start > end
        self.assertEqual(tree.range(D - timedelta(days=9), D - timedelta(days=1)), [])  # all before
        self.assertEqual(tree.range(D + timedelta(days=20), D + timedelta(days=30)), [])  # all after

    def test_sorted_inserts_stay_balanced(self):
        """A whole year planned in date order would make a plain BST a chain."""
        tree = DateAVLTree()
        for offset in range(365):
            tree.set_meal(D + timedelta(days=offset), "Lunch", "Adobo", 8000)
        check_date_tree(tree)
        self.assertLessEqual(tree.height(), 11)                 # about 1.44 * log2(365)

    def test_two_children_delete_keeps_meals_with_their_date(self):
        tree = DateAVLTree()
        for offset in (4, 2, 6, 1, 3, 5, 7):
            tree.set_meal(D + timedelta(days=offset), "Lunch", f"Food {offset}", 100 * offset)
        root_day = tree.root.day
        tree.remove_meal(root_day, "Lunch")
        check_date_tree(tree)
        for node in tree.inorder():
            offset = (node.day - D).days
            self.assertEqual(node.meals["Lunch"], (f"Food {offset}", 100 * offset))


class DateTreeRandomTests(unittest.TestCase):
    def test_matches_brute_force_on_random_changes(self):
        rng = random.Random(2026)
        tree, model = DateAVLTree(), {}                         # model: date -> {category: (name, price)}
        categories = ("Breakfast", "Lunch", "Dinner", "Snacks")
        for step in range(3000):
            day = D + timedelta(days=rng.randrange(300))
            category = rng.choice(categories)
            if rng.random() < 0.6:
                price = rng.randint(1, 50000)
                tree.set_meal(day, category, f"F{step}", price)
                model.setdefault(day, {})[category] = (f"F{step}", price)
            else:
                expected = model.get(day, {}).pop(category, None)
                self.assertEqual(tree.remove_meal(day, category), expected)
                if day in model and not model[day]:
                    del model[day]
            if step % 250 == 0:
                check_date_tree(tree)
        check_date_tree(tree)
        self.assertEqual(len(tree), len(model))
        for _ in range(300):
            a = D + timedelta(days=rng.randrange(-10, 310))
            b = a + timedelta(days=rng.randrange(0, 60))
            expected = sorted(d for d in model if a <= d <= b)
            self.assertEqual([n.day for n in tree.range(a, b)], expected)
            self.assertEqual(tree.range_total(a, b),
                             sum(p for d in expected for _, p in model[d].values()))


if __name__ == "__main__":
    unittest.main()
