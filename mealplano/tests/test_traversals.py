"""Milestone 3 tests: LinkedQueue and the four traversals (FR-5, FR-7)."""

import random
import unittest

from mealplano.dsa import AVLTree, BST, LinkedQueue


class LinkedQueueTests(unittest.TestCase):
    def test_fifo_order(self):
        q = LinkedQueue()
        for x in [1, 2, 3]:
            q.enqueue(x)
        self.assertEqual(len(q), 3)
        self.assertEqual(q.peek(), 1)
        self.assertEqual([q.dequeue(), q.dequeue(), q.dequeue()], [1, 2, 3])
        self.assertTrue(q.is_empty())

    def test_empty_queue_raises(self):
        q = LinkedQueue()
        with self.assertRaises(IndexError):
            q.dequeue()
        with self.assertRaises(IndexError):
            q.peek()

    def test_reuse_after_emptying(self):
        # Checks the tail pointer is reset when the queue empties.
        q = LinkedQueue()
        q.enqueue("a")
        q.dequeue()
        q.enqueue("b")
        q.enqueue("c")
        self.assertEqual([q.dequeue(), q.dequeue()], ["b", "c"])

    def test_interleaved_matches_python_list(self):
        rng = random.Random(3)
        q, model = LinkedQueue(), []
        for i in range(2000):
            if model and rng.random() < 0.45:
                self.assertEqual(q.dequeue(), model.pop(0))
            else:
                q.enqueue(i)
                model.append(i)
            self.assertEqual(len(q), len(model))


class SharedTraversalTests:
    tree_class = None

    def setUp(self):
        #            m
        #        f       t
        #      c   h   r   w
        # Inserted level by level, so BST and AVL both give this exact shape.
        self.tree = self.tree_class()
        for k in ["m", "f", "t", "c", "h", "r", "w"]:
            self.tree.insert(k, 100)

    def keys(self, nodes):
        return "".join(n.key for n in nodes)

    def test_known_seven_node_tree(self):
        self.assertEqual(self.keys(self.tree.inorder()), "cfhmrtw")
        self.assertEqual(self.keys(self.tree.preorder()), "mfchtrw")
        self.assertEqual(self.keys(self.tree.postorder()), "chfrwtm")
        self.assertEqual(self.keys(self.tree.levelorder()), "mftchrw")

    def test_empty_tree(self):
        empty = self.tree_class()
        for order in (empty.inorder, empty.preorder, empty.postorder, empty.levelorder):
            self.assertEqual(order(), [])

    def test_one_node_tree(self):
        one = self.tree_class()
        one.insert("Adobo", 8000)
        for order in (one.inorder, one.preorder, one.postorder, one.levelorder):
            self.assertEqual(self.keys(order()), "adobo")

    def test_every_traversal_visits_every_node_once(self):
        tree = self.tree_class()
        rng = random.Random(5)
        for _ in range(500):
            tree.insert(f"f{rng.randint(0, 10**6)}", 100)
        expected = sorted(n.key for n in tree.inorder())
        for order in (tree.preorder, tree.postorder, tree.levelorder):
            self.assertEqual(sorted(n.key for n in order()), expected)

    def test_preorder_root_first_postorder_root_last(self):
        root = self.tree.root.key
        self.assertEqual(self.tree.preorder()[0].key, root)
        self.assertEqual(self.tree.postorder()[-1].key, root)
        self.assertEqual(self.tree.levelorder()[0].key, root)


class BSTTraversalTests(SharedTraversalTests, unittest.TestCase):
    tree_class = BST

    def test_1000_node_chain_no_recursion_error(self):
        tree = BST()
        for i in range(1000):
            tree.insert(f"food{i:04d}", 100)
        for order in (tree.preorder, tree.postorder, tree.levelorder):
            self.assertEqual(len(order()), 1000)


class AVLTraversalTests(SharedTraversalTests, unittest.TestCase):
    tree_class = AVLTree


if __name__ == "__main__":
    unittest.main()
