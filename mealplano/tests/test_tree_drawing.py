"""Tests for the Tree view drawing (stretch goal)."""

import html
import unittest

from mealplano.dsa import AVLTree
from mealplano.dsa.avl import balance_factor
from mealplano.tests.test_food_routes import FoodPageCase
from mealplano.tree_drawing import BOX_H, MAX_LEVELS, layout


def perfect_tree():
    #            m
    #        f       t
    #      c   h   r   w
    tree = AVLTree()
    for key in ["m", "f", "t", "c", "h", "r", "w"]:
        tree.insert(key, 100)
    return tree


class LayoutTests(unittest.TestCase):
    def test_empty_tree_has_no_drawing(self):
        self.assertIsNone(layout(AVLTree()))

    def test_x_follows_in_order_and_y_follows_depth(self):
        d = layout(perfect_tree())
        self.assertEqual([n["key"] for n in d["nodes"]], list("cfhmrtw"))     # in-order
        xs = [n["x"] for n in d["nodes"]]
        self.assertEqual(xs, sorted(xs))                                       # left to right
        self.assertEqual(len(set(xs)), 7)                                      # no two boxes share a column
        depth = {n["key"]: n["depth"] for n in d["nodes"]}
        self.assertEqual(depth, {"m": 0, "f": 1, "t": 1, "c": 2, "h": 2, "r": 2, "w": 2})
        self.assertEqual(d["root_x"], d["nodes"][3]["x"])
        self.assertFalse(d["truncated"])
        self.assertEqual(d["stubs"], [])

    def test_edges_join_each_child_to_its_parent(self):
        d = layout(perfect_tree())
        at = {(n["x"], n["y"]): n["key"] for n in d["nodes"]}
        bottom = {(n["x"], n["y"] + BOX_H): n["key"] for n in d["nodes"]}
        pairs = {(bottom[(e["x1"], e["y1"])], at[(e["x2"], e["y2"])]) for e in d["edges"]}
        self.assertEqual(pairs, {("m", "f"), ("m", "t"), ("f", "c"), ("f", "h"),
                                 ("t", "r"), ("t", "w")})

    def test_visit_numbers_and_balance_factors(self):
        tree = perfect_tree()
        tree.insert("a", 100)                          # makes c lean left, f lean left
        d = layout(tree, [n.key for n in tree.preorder()])
        order = {n["key"]: n["order"] for n in d["nodes"]}
        self.assertEqual(order["m"], 1)
        self.assertEqual(order["f"], 2)
        for n in d["nodes"]:
            self.assertEqual(n["bf"], balance_factor(tree.search(n["key"])))
        self.assertEqual({n["key"]: n["bf"] for n in d["nodes"]}["c"], 1)

    def test_big_tree_draws_top_levels_and_counts_the_rest(self):
        tree = AVLTree()
        for i in range(100):
            tree.insert(f"food{i:03d}", 100)            # sorted input: AVL stays balanced
        d = layout(tree)
        self.assertTrue(d["truncated"])
        self.assertEqual(d["levels_drawn"], MAX_LEVELS)
        self.assertLessEqual(d["shown"], 2 ** MAX_LEVELS - 1)
        hidden = sum(s["count"] for s in d["stubs"])
        self.assertEqual(d["shown"] + hidden, 100)      # every food is either drawn or counted
        self.assertTrue(all(n["depth"] < MAX_LEVELS for n in d["nodes"]))

    def test_long_names_are_shortened(self):
        tree = AVLTree()
        tree.insert("Chicken Inasal Extra Rice Combo", 15500)
        node = layout(tree)["nodes"][0]
        self.assertEqual(node["name"], "Chicken Inasal Extra Rice Combo")
        self.assertEqual(node["short"], "Chicken Inasa…")


class TreePageTests(FoodPageCase):
    def test_tree_page_draws_svg(self):
        for name, price in [("Menudo", 8500), ("Laing", 6000), ("Sisig", 11000),
                            ("Chicken Inasal Extra Rice Combo", 15500)]:
            self.service.add_food(self.uid, "Dinner", name, price)
        page = self.client.get("/tree?category=Dinner&order=preorder").get_data(as_text=True)
        self.assertIn('<svg class="tree-svg"', page)
        self.assertEqual(page.count('<g class="tree-node'), 4)
        self.assertIn("tree-root", page)
        self.assertIn("Chicken Inasal Extra Rice Combo ·", page)      # full name in tooltip
        self.assertIn("Chicken Inasa…", page)                          # short name in box
        self.assertIn("/static/tree.js", page)
        self.assertIn("visit order for pre-order", page)

    def test_empty_category_has_no_svg(self):
        page = self.client.get("/tree?category=Snacks").get_data(as_text=True)
        self.assertNotIn("<svg", page)
        self.assertIn("Snacks is empty.", page)

    def test_names_are_escaped_inside_the_drawing(self):
        self.service.add_food(self.uid, "Snacks", "<b>x</b>", 100)
        page = self.client.get("/tree?category=Snacks").get_data(as_text=True)
        self.assertNotIn("<b>x</b>", page)
        self.assertIn(html.escape("<b>x</b>"), page)

    def test_big_tree_caption(self):
        for i in range(40):
            self.service.add_food(self.uid, "Lunch", f"Dish {i:02d}", 100 + i)
        page = self.client.get("/tree?category=Lunch&order=levelorder").get_data(as_text=True)
        self.assertIn("Showing the top 4 of", page)
        self.assertIn("of 40 foods", page)


if __name__ == "__main__":
    unittest.main()
