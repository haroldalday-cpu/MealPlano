"""Milestone 1 tests: insert, search, in-order traversal, and balancing.

Run from the project folder:
    python -m unittest discover -s mealplano/tests -t . -v
"""

import math
import random
import unittest

from mealplano.dsa import AVLTree, BST, FoodNode
from mealplano.dsa.avl import balance_factor
from mealplano.tests.helpers import check_tree


class SharedTreeTests:
    """Tests both trees must pass. Subclasses set tree_class."""

    tree_class = None

    def setUp(self):
        self.tree = self.tree_class()

    # ---- insert: normal ----
    def test_insert_and_search_adobo(self):
        self.assertTrue(self.tree.insert("Adobo", 8000))
        node = self.tree.search("Adobo")
        self.assertEqual(node.display_name, "Adobo")
        self.assertEqual(node.price, 8000)
        check_tree(self.tree)

    def test_inorder_is_alphabetical(self):
        for name in ["Sinigang", "Adobo", "Tinola", "Kare-Kare", "Bulalo"]:
            self.tree.insert(name, 10000)
        names = [n.display_name for n in self.tree.inorder()]
        self.assertEqual(names, ["Adobo", "Bulalo", "Kare-Kare", "Sinigang", "Tinola"])
        check_tree(self.tree)

    # ---- insert: boundary ----
    def test_first_food_in_empty_tree_becomes_root(self):
        self.tree.insert("Adobo", 8000)
        self.assertEqual(self.tree.root.key, "adobo")
        self.assertEqual(len(self.tree), 1)
        self.assertEqual(self.tree.height(), 1)

    def test_case_insensitive_key_keeps_display_name(self):
        self.tree.insert("  Pancit Canton ", 4500)
        node = self.tree.search("PANCIT canton")
        self.assertEqual(node.key, "pancit canton")
        self.assertEqual(node.display_name, "Pancit Canton")

    # ---- insert: invalid ----
    def test_duplicate_rejected_any_case(self):
        self.assertTrue(self.tree.insert("Adobo", 8000))
        self.assertFalse(self.tree.insert("adobo", 9000))
        self.assertEqual(len(self.tree), 1)
        self.assertEqual(self.tree.search("Adobo").price, 8000)   # original kept
        check_tree(self.tree)

    def test_invalid_inputs_raise_value_error(self):
        for name, price in [("", 100), ("   ", 100), ("Adobo", 0),
                            ("Adobo", -5), ("Adobo", "abc"), ("Adobo", 80.5),
                            ("Adobo", True), (None, 100)]:
            with self.subTest(name=name, price=price):
                with self.assertRaises(ValueError):
                    self.tree.insert(name, price)
        self.assertEqual(len(self.tree), 0)

    # ---- search ----
    def test_search_missing_returns_none(self):
        self.tree.insert("Adobo", 8000)
        self.assertIsNone(self.tree.search("Sinigang"))

    def test_search_empty_tree(self):
        self.assertIsNone(self.tree.search("Adobo"))
        self.assertEqual(self.tree.inorder(), [])
        self.assertEqual(self.tree.height(), 0)

    def test_search_root_smallest_and_largest(self):
        for name in ["Menudo", "Adobo", "Ziti", "Lechon", "Bistek"]:
            self.tree.insert(name, 10000)
        names = [n.key for n in self.tree.inorder()]
        for key in [self.tree.root.key, names[0], names[-1]]:
            self.assertIsNotNone(self.tree.search(key))

    # ---- large / random ----
    def test_1000_alphabetical_inserts_no_recursion_error(self):
        names = [f"food{i:04d}" for i in range(1000)]   # already in sorted order
        for name in names:
            self.tree.insert(name, 100)
        self.assertEqual(len(self.tree), 1000)
        for name in names[::97]:
            self.assertIsNotNone(self.tree.search(name))
        check_tree(self.tree)

    def test_random_inserts_match_dict(self):
        rng = random.Random(42)
        oracle = {}
        for _ in range(1000):
            name = f"food{rng.randint(0, 600)}"
            price = rng.randint(1, 100000)
            inserted = self.tree.insert(name, price)
            self.assertEqual(inserted, name not in oracle)
            oracle.setdefault(name, price)
        check_tree(self.tree)
        self.assertEqual({n.key: n.price for n in self.tree.inorder()}, oracle)


class BSTTests(SharedTreeTests, unittest.TestCase):
    tree_class = BST

    def test_sorted_input_is_worst_case(self):
        # Alphabetical input makes the plain BST a chain: height == n.
        for i in range(1000):
            self.tree.insert(f"food{i:04d}", 100)
        self.assertEqual(self.tree.height(), 1000)


class AVLTests(SharedTreeTests, unittest.TestCase):
    tree_class = AVLTree

    def test_fr19_sorted_input_height_bound(self):
        # FR-19 acceptance: 1,000 alphabetical inserts give height <= 1.44 * log2(1001)
        for i in range(1000):
            self.tree.insert(f"food{i:04d}", 100)
            if i % 50 == 0:
                check_tree(self.tree)
        self.assertLessEqual(self.tree.height(), 1.44 * math.log2(1001))
        check_tree(self.tree)

    def test_all_four_rotation_cases(self):
        # Each list of three inserts triggers exactly one rotation case.
        cases = {
            "LL": ["c", "b", "a"],
            "RR": ["a", "b", "c"],
            "LR": ["c", "a", "b"],
            "RL": ["a", "c", "b"],
        }
        for case, keys in cases.items():
            with self.subTest(case=case):
                tree = AVLTree()
                for k in keys:
                    tree.insert(k, 100)
                self.assertEqual(tree.root.key, "b")
                self.assertEqual(tree.root.left.key, "a")
                self.assertEqual(tree.root.right.key, "c")
                self.assertEqual(tree.height(), 2)
                check_tree(tree)

    def test_balance_factor_every_node(self):
        rng = random.Random(7)
        for _ in range(300):
            self.tree.insert(f"x{rng.randint(0, 10**6)}", 100)
        for node in self.tree.inorder():
            self.assertIn(balance_factor(node), (-1, 0, 1))


class CheckTreeCatchesBugs(unittest.TestCase):
    """Make sure the helper itself fails on broken trees."""

    def test_detects_unsorted_tree(self):
        tree = BST()
        tree.insert("m", 100)
        tree.root.left = FoodNode("z", 100)   # wrong side on purpose
        tree.size = 2
        with self.assertRaises(AssertionError):
            check_tree(tree)

    def test_detects_wrong_height_and_imbalance(self):
        tree = AVLTree()
        tree.insert("b", 100)
        tree.insert("a", 100)
        tree.root.height = 5                   # stale height
        with self.assertRaises(AssertionError):
            check_tree(tree)

        tree = AVLTree()
        tree.root = FoodNode("a", 100)         # hand-built chain a -> b -> c
        tree.root.right = FoodNode("b", 100)
        tree.root.right.right = FoodNode("c", 100)
        tree.root.right.height = 2
        tree.root.height = 3
        tree.size = 3
        with self.assertRaises(AssertionError):
            check_tree(tree)


if __name__ == "__main__":
    unittest.main()
