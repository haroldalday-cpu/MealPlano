"""Milestone 3 tests: LinkedStack and UndoHistory (FR-18)."""

import random
import unittest

from mealplano.dsa import CATEGORIES, AVLTree, LinkedStack, UndoHistory
from mealplano.tests.helpers import check_tree, shape


class LinkedStackTests(unittest.TestCase):
    def test_lifo_order(self):
        s = LinkedStack()
        for x in [1, 2, 3]:
            s.push(x)
        self.assertEqual(s.peek(), 3)
        self.assertEqual([s.pop(), s.pop(), s.pop()], [3, 2, 1])
        self.assertTrue(s.is_empty())

    def test_empty_stack_raises(self):
        s = LinkedStack()
        with self.assertRaises(IndexError):
            s.pop()
        with self.assertRaises(IndexError):
            s.peek()

    def test_capacity_drops_oldest(self):
        s = LinkedStack(capacity=3)
        for x in range(1, 6):                    # push 1..5
            s.push(x)
        self.assertEqual(len(s), 3)
        self.assertEqual([s.pop(), s.pop(), s.pop()], [5, 4, 3])   # 1 and 2 were dropped
        self.assertTrue(s.is_empty())

    def test_capacity_one(self):
        s = LinkedStack(capacity=1)
        s.push("a")
        s.push("b")
        self.assertEqual(len(s), 1)
        self.assertEqual(s.pop(), "b")
        s.push("c")                              # still works after emptying
        self.assertEqual(s.pop(), "c")

    def test_invalid_capacity(self):
        with self.assertRaises(ValueError):
            LinkedStack(capacity=0)

    def test_clear(self):
        s = LinkedStack()
        s.push(1)
        s.push(2)
        s.clear()
        self.assertTrue(s.is_empty())
        s.push(3)
        self.assertEqual(s.pop(), 3)

    def test_interleaved_capped_matches_model(self):
        rng = random.Random(9)
        s, model = LinkedStack(capacity=20), []
        for i in range(3000):
            if model and rng.random() < 0.4:
                self.assertEqual(s.pop(), model.pop())
            else:
                s.push(i)
                model.append(i)
                if len(model) > 20:
                    model.pop(0)
            self.assertEqual(len(s), len(model))


class UndoHistoryTests(unittest.TestCase):
    """Mirrors how the food service will use it: change the tree, then record the inverse."""

    def setUp(self):
        self.trees = {c: AVLTree() for c in CATEGORIES}
        self.history = UndoHistory(limit=20)
        for name, price in [("Menudo", 9000), ("Adobo", 8000), ("Tinola", 7500)]:
            self.trees["Lunch"].insert(name, price)

    def add(self, category, name, price):
        if self.trees[category].insert(name, price):
            self.history.record_add(category, name)

    def delete(self, category, name):
        removed = self.trees[category].delete(name)
        if removed:
            self.history.record_delete(category, removed[0], removed[1])

    def update(self, category, name, price):
        old = self.trees[category].update(name, price)
        if old is not None:
            self.history.record_update(category, name, old)

    def test_fr18_add_then_undo(self):
        before = shape(self.trees["Lunch"])
        self.add("Lunch", "Sinigang", 12000)
        entry = self.history.undo(self.trees)
        self.assertEqual(entry, ("delete", "Lunch", "Sinigang", None))
        self.assertEqual(shape(self.trees["Lunch"]), before)
        check_tree(self.trees["Lunch"])

    def test_fr18_delete_then_undo_restores_name_category_price(self):
        self.delete("Lunch", "adobo")                  # lowercase on purpose
        self.assertIsNone(self.trees["Lunch"].search("Adobo"))
        entry = self.history.undo(self.trees)
        self.assertEqual(entry, ("add", "Lunch", "Adobo", 8000))
        node = self.trees["Lunch"].search("Adobo")
        self.assertEqual((node.display_name, node.price), ("Adobo", 8000))   # capitals kept
        check_tree(self.trees["Lunch"])

    def test_undo_update_restores_old_price(self):
        self.update("Lunch", "Adobo", 8500)
        self.history.undo(self.trees)
        self.assertEqual(self.trees["Lunch"].search("Adobo").price, 8000)

    def test_undo_two_children_delete(self):
        root = self.trees["Lunch"].root            # Menudo, which has two children
        name, price = root.display_name, root.price
        self.delete("Lunch", name)
        self.history.undo(self.trees)
        self.assertEqual(self.trees["Lunch"].search(name).price, price)
        check_tree(self.trees["Lunch"])

    def test_undo_is_last_in_first_out_across_categories(self):
        self.add("Breakfast", "Tapsilog", 9500)
        self.add("Snacks", "Turon", 2000)
        self.update("Lunch", "Tinola", 7000)
        self.assertEqual(self.history.undo(self.trees)[0:2], ("update", "Lunch"))
        self.assertEqual(self.history.undo(self.trees)[0:2], ("delete", "Snacks"))
        self.assertEqual(self.history.undo(self.trees)[0:2], ("delete", "Breakfast"))
        self.assertEqual(len(self.trees["Breakfast"]), 0)
        self.assertEqual(len(self.trees["Snacks"]), 0)
        self.assertEqual(self.trees["Lunch"].search("Tinola").price, 7500)

    def test_undo_with_empty_history(self):
        self.assertIsNone(self.history.undo(self.trees))

    def test_undo_limit_is_20(self):
        for i in range(25):
            self.add("Dinner", f"dish{i:02d}", 100 + i)
        self.assertEqual(len(self.history), 20)
        for _ in range(20):
            self.assertIsNotNone(self.history.undo(self.trees))
        self.assertIsNone(self.history.undo(self.trees))     # 21st undo: nothing left
        # The 5 oldest adds can no longer be undone, so they remain.
        self.assertEqual([n.key for n in self.trees["Dinner"].inorder()],
                         [f"dish{i:02d}" for i in range(5)])

    def test_clear_on_logout(self):
        self.add("Lunch", "Sinigang", 12000)
        self.history.clear()
        self.assertIsNone(self.history.undo(self.trees))
        self.assertIsNotNone(self.trees["Lunch"].search("Sinigang"))

    def test_random_changes_then_undo_all_restores_start(self):
        rng = random.Random(11)
        start = {c: {n.key: n.price for n in t.inorder()} for c, t in self.trees.items()}
        history = UndoHistory(limit=1000)
        self.history = history
        for _ in range(300):
            category = rng.choice(CATEGORIES)
            name = f"food{rng.randint(0, 40)}"
            op = rng.choice(["add", "delete", "update"])
            if op == "add":
                self.add(category, name, rng.randint(1, 50000))
            elif op == "delete":
                self.delete(category, name)
            else:
                self.update(category, name, rng.randint(1, 50000))
        while history.undo(self.trees) is not None:
            pass
        now = {c: {n.key: n.price for n in t.inorder()} for c, t in self.trees.items()}
        self.assertEqual(now, start)
        for tree in self.trees.values():
            check_tree(tree)


if __name__ == "__main__":
    unittest.main()
