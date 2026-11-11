"""Milestone 2 tests: delete (FR-4), price update (FR-8), randomised dict oracle.

Run from the project folder:
    python -m unittest discover -s mealplano/tests -t . -v
"""

import math
import random
import unittest

from mealplano.dsa import AVLTree, BST
from mealplano.tests.helpers import check_tree, shape


def keys_of(tree):
    return [n.key for n in tree.inorder()]


def child_case(node):
    children = (node.left is not None) + (node.right is not None)
    return ["leaf", "one child", "two children"][children]


class SharedDeleteUpdateTests:
    tree_class = None

    def setUp(self):
        self.tree = self.tree_class()

    def build(self, names):
        for i, name in enumerate(names):
            self.tree.insert(name, 1000 + i)
        check_tree(self.tree)

    # ---------- delete: the three cases ----------
    def test_delete_leaf(self):
        self.build(["m", "f", "t"])
        self.assertEqual(self.tree.delete("f"), ("f", 1001))
        self.assertEqual(keys_of(self.tree), ["m", "t"])
        check_tree(self.tree)

    def test_delete_one_child(self):
        self.build(["m", "f", "t", "w"])          # t has one child, w
        self.tree.delete("t")
        self.assertEqual(keys_of(self.tree), ["f", "m", "w"])
        self.assertIsNotNone(self.tree.search("w"))
        check_tree(self.tree)

    def test_delete_two_children_successor_is_right_child(self):
        self.build(["m", "f", "t", "c", "h"])     # f has children c and h; successor is h
        self.assertEqual(self.tree.delete("f"), ("f", 1001))
        self.assertEqual(keys_of(self.tree), ["c", "h", "m", "t"])
        check_tree(self.tree)

    def test_delete_two_children_successor_deeper(self):
        # The successor of m is p, two levels down the right subtree, and p has a right child q.
        self.build(["m", "f", "t", "c", "h", "r", "w", "p", "s", "q"])
        removed = self.tree.delete("m")
        self.assertEqual(removed, ("m", 1000))     # reports m, not the successor p
        self.assertEqual(keys_of(self.tree), sorted("fchtrwpsq"))
        node = self.tree.search("p")
        self.assertEqual(node.price, 1007)         # successor kept its own price
        check_tree(self.tree)

    def test_acceptance_fr4_all_three_cases(self):
        names = ["Menudo", "Adobo", "Tinola", "Bistek", "Lechon", "Sinigang", "Ziti",
                 "Kare-Kare", "Arroz Caldo", "Champorado", "Dinuguan", "Embutido"]
        self.build(names)
        expected = {n.lower() for n in names}
        cases_seen = set()
        # Delete one node of each kind, choosing it from the tree's current shape.
        for case in ["one child", "two children", "leaf"]:
            target = next(n for n in self.tree.inorder() if child_case(n) == case)
            cases_seen.add(case)
            # Save the key first: a two-children delete copies the successor's
            # data into this node, so target.key changes during the delete.
            key = target.key
            self.tree.delete(key)
            expected.discard(key)
            self.assertIsNone(self.tree.search(key))
            check_tree(self.tree)
            self.assertEqual(set(keys_of(self.tree)), expected)   # no other food lost
        self.assertEqual(cases_seen, {"leaf", "one child", "two children"})

    # ---------- delete: boundary and invalid ----------
    def test_delete_root(self):
        self.build(["m", "f", "t"])
        root = self.tree.root.key
        self.tree.delete(root)
        self.assertIsNone(self.tree.search(root))
        self.assertEqual(len(self.tree), 2)
        check_tree(self.tree)

    def test_delete_only_node(self):
        self.build(["Adobo"])
        self.assertEqual(self.tree.delete("adobo"), ("Adobo", 1000))
        self.assertIsNone(self.tree.root)
        self.assertEqual(len(self.tree), 0)
        self.assertEqual(self.tree.height(), 0)

    def test_delete_missing_food(self):
        self.build(["m", "f", "t"])
        before = shape(self.tree)
        self.assertIsNone(self.tree.delete("zzz"))
        self.assertIsNone(BST().delete("anything"))
        self.assertEqual(shape(self.tree), before)
        self.assertEqual(len(self.tree), 3)

    def test_delete_is_case_insensitive(self):
        self.build(["Pancit Canton"])
        self.assertEqual(self.tree.delete("  PANCIT canton "), ("Pancit Canton", 1000))

    def test_delete_everything(self):
        names = [f"food{i:03d}" for i in range(200)]
        self.build(names)
        random.Random(1).shuffle(names)
        for name in names:
            self.assertIsNotNone(self.tree.delete(name))
            check_tree(self.tree)
        self.assertIsNone(self.tree.root)

    # ---------- update ----------
    def test_update_price(self):
        self.tree.insert("Adobo", 8000)
        self.assertEqual(self.tree.update("Adobo", 8500), 8000)   # returns old price
        self.assertEqual(self.tree.search("adobo").price, 8500)

    def test_update_does_not_change_shape(self):
        self.build(["m", "f", "t", "c", "h", "r", "w"])
        before = shape(self.tree)
        self.tree.update("h", 99999)
        self.tree.update(self.tree.root.key, 1)                   # boundary: update the root
        self.assertEqual(shape(self.tree), before)
        self.assertEqual(self.tree.search("h").price, 99999)
        self.assertEqual(self.tree.root.price, 1)
        check_tree(self.tree)

    def test_update_missing_food(self):
        self.build(["m"])
        self.assertIsNone(self.tree.update("zzz", 500))

    def test_update_invalid_price(self):
        self.tree.insert("Adobo", 8000)
        for bad in [0, -100, "abc", 80.5, None, True]:
            with self.subTest(price=bad):
                with self.assertRaises(ValueError):
                    self.tree.update("Adobo", bad)
        self.assertEqual(self.tree.search("Adobo").price, 8000)   # unchanged

    # ---------- randomised oracle test (PRD Section 10) ----------
    def test_1000_random_operations_match_dict(self):
        rng = random.Random(42)
        oracle = {}
        for step in range(1000):
            name = f"food{rng.randint(0, 150)}"
            op = rng.choice(["insert", "insert", "delete", "update"])
            if op == "insert":
                price = rng.randint(1, 100000)
                ok = self.tree.insert(name, price)
                self.assertEqual(ok, name not in oracle, f"step {step}")
                oracle.setdefault(name, price)
            elif op == "delete":
                removed = self.tree.delete(name)
                expected = (name, oracle.pop(name)) if name in oracle else None
                self.assertEqual(removed, expected, f"step {step}")
            else:
                price = rng.randint(1, 100000)
                old = self.tree.update(name, price)
                self.assertEqual(old, oracle.get(name), f"step {step}")
                if name in oracle:
                    oracle[name] = price
            check_tree(self.tree)
            self.assertEqual({n.key: n.price for n in self.tree.inorder()}, oracle,
                             f"step {step} ({op} {name})")


class BSTDeleteUpdateTests(SharedDeleteUpdateTests, unittest.TestCase):
    tree_class = BST

    def test_delete_in_1000_node_chain_no_recursion_error(self):
        for i in range(1000):
            self.tree.insert(f"food{i:04d}", 100)
        self.assertEqual(self.tree.delete("food0999"), ("food0999", 100))   # deepest leaf
        self.assertEqual(self.tree.delete("food0000"), ("food0000", 100))   # root
        self.assertEqual(len(self.tree), 998)
        check_tree(self.tree)


class AVLDeleteUpdateTests(SharedDeleteUpdateTests, unittest.TestCase):
    tree_class = AVLTree

    def test_delete_triggers_rotation(self):
        # Deleting a makes b's right side two taller, forcing a rotation at the root.
        self.build(["b", "a", "c", "d"])
        self.tree.delete("a")
        self.assertEqual(self.tree.root.key, "c")
        self.assertEqual(self.tree.height(), 2)
        check_tree(self.tree)

    def test_height_stays_logarithmic_after_many_deletes(self):
        names = [f"food{i:04d}" for i in range(2000)]
        self.build(names)
        for name in names[::2]:                     # delete every other food
            self.tree.delete(name)
        check_tree(self.tree)
        self.assertEqual(len(self.tree), 1000)
        self.assertLessEqual(self.tree.height(), 1.44 * math.log2(1001))


if __name__ == "__main__":
    unittest.main()
