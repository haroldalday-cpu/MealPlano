"""Tests for PriceAVLTree: the app's category trees, ordered by (price, name)."""

import math
import random
import unittest

from mealplano.dsa import PriceAVLTree, cheapest_food
from mealplano.tests.helpers import check_tree, shape


def names(nodes):
    return [n.display_name for n in nodes]


class PriceOrderTests(unittest.TestCase):
    def setUp(self):
        self.tree = PriceAVLTree()
        for name, price in [("Sinigang", 12000), ("Adobo", 8050), ("Tinola", 7500),
                            ("Kare-Kare", 15000), ("Bicol Express", 7500), ("Pancit Canton", 6500)]:
            self.assertTrue(self.tree.insert(name, price))
        check_tree(self.tree)

    def test_inorder_is_cheapest_first_ties_alphabetical(self):
        self.assertEqual(names(self.tree.inorder()),
                         ["Pancit Canton", "Bicol Express", "Tinola", "Adobo", "Sinigang", "Kare-Kare"])
        self.assertEqual(self.tree.root.key[0], self.tree.root.price)     # key = (price, name)

    def test_cheapest_is_leftmost(self):
        self.assertEqual(self.tree.cheapest().display_name, "Pancit Canton")
        self.assertEqual(cheapest_food(self.tree), ("Pancit Canton", 6500))
        self.assertIsNone(PriceAVLTree().cheapest())
        self.assertIsNone(cheapest_food(PriceAVLTree()))

    def test_search_by_name_any_case(self):
        node = self.tree.search("  bicol EXPRESS ")
        self.assertEqual((node.display_name, node.price), ("Bicol Express", 7500))
        self.assertIsNone(self.tree.search("Lechon"))
        self.assertIsNone(PriceAVLTree().search("Adobo"))

    def test_search_exact(self):
        self.assertEqual(self.tree.search_exact(7500, "tinola").display_name, "Tinola")
        self.assertIsNone(self.tree.search_exact(7600, "Tinola"))         # right name, wrong price

    def test_duplicate_name_rejected_even_at_another_price(self):
        self.assertFalse(self.tree.insert("adobo", 9999))
        self.assertEqual(len(self.tree), 6)
        self.assertEqual(self.tree.search("Adobo").price, 8050)
        check_tree(self.tree)

    def test_same_price_different_names_allowed(self):
        self.assertTrue(self.tree.insert("Laing", 7500))
        tied = [n.display_name for n in self.tree.inorder() if n.price == 7500]
        self.assertEqual(tied, ["Bicol Express", "Laing", "Tinola"])

    def test_update_moves_the_food(self):
        before = shape(self.tree)
        self.assertEqual(self.tree.update("Kare-Kare", 5000), 15000)       # most expensive -> cheapest
        self.assertEqual(self.tree.cheapest().display_name, "Kare-Kare")
        self.assertNotEqual(shape(self.tree), before)
        self.assertEqual(len(self.tree), 6)
        check_tree(self.tree)

    def test_update_same_price_keeps_shape(self):
        before = shape(self.tree)
        self.assertEqual(self.tree.update("Adobo", 8050), 8050)
        self.assertEqual(shape(self.tree), before)

    def test_update_missing_and_invalid(self):
        self.assertIsNone(self.tree.update("Lechon", 100))
        for bad in [0, -1, "abc", 1.5, True]:
            with self.assertRaises(ValueError):
                self.tree.update("Adobo", bad)
        self.assertEqual(self.tree.search("Adobo").price, 8050)

    def test_delete_by_name_all_cases(self):
        for pick in ["pancit canton", "Kare-Kare", None]:      # None = whatever is the root now
            food = pick or self.tree.root.display_name
            removed = self.tree.delete(food)
            self.assertIsNotNone(removed)
            self.assertIsNone(self.tree.search(removed[0]))
            check_tree(self.tree)
        self.assertIsNone(self.tree.delete("Lechon"))
        self.assertEqual(len(self.tree), 3)

    def test_two_children_delete_keeps_name_key_with_its_food(self):
        # Deleting a node with two children copies the successor's data into
        # it; name_key must move too, or name search finds the wrong food.
        root = self.tree.root.display_name
        self.tree.delete(root)
        for node in self.tree.inorder():
            self.assertEqual(node.name_key, node.display_name.lower())
            self.assertIs(self.tree.search(node.display_name), node)


class PriceTreeScaleTests(unittest.TestCase):
    def test_sorted_prices_stay_balanced(self):
        tree = PriceAVLTree()
        for i in range(1000):
            tree.insert(f"food{i:04d}", 100 + i)           # increasing prices: BST worst case
        check_tree(tree)
        self.assertLessEqual(tree.height(), 1.44 * math.log2(1001))

    def test_1000_random_operations_match_dict(self):
        rng = random.Random(42)
        tree, oracle = PriceAVLTree(), {}
        for step in range(1000):
            name = f"food{rng.randint(0, 120)}"
            op = rng.choice(["insert", "insert", "delete", "update"])
            price = rng.choice([500, 1000, 1500, rng.randint(1, 50000)])    # many ties
            if op == "insert":
                self.assertEqual(tree.insert(name, price), name not in oracle, f"step {step}")
                oracle.setdefault(name, price)
            elif op == "delete":
                expected = (name, oracle.pop(name)) if name in oracle else None
                self.assertEqual(tree.delete(name), expected, f"step {step}")
            else:
                self.assertEqual(tree.update(name, price), oracle.get(name), f"step {step}")
                if name in oracle:
                    oracle[name] = price
            check_tree(tree)
            listed = [(n.display_name, n.price) for n in tree.inorder()]
            self.assertEqual(listed, sorted(oracle.items(), key=lambda kv: (kv[1], kv[0])), f"step {step}")


if __name__ == "__main__":
    unittest.main()
