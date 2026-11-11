"""Keeps each user's trees and SQLite in sync, and owns the in-memory cache (PRD Section 11).

Rules:
  - A change (add, delete, update, undo) is validated, written to SQLite FIRST,
    then applied to the tree, then its inverse is pushed onto the undo stack.
    If the SQLite write fails, the tree is never touched.
  - A read (search, menu, sort, total, budget, tree view) uses the trees only.
  - A user's trees are rebuilt from SQLite on login, or on first use after a
    server restart. Logout drops them and the undo history.

The cache lives in one Python process, so the app runs with a single worker
(local demo only). A lock stops two requests changing the same cache at once.
"""

import threading

from mealplano import db
from mealplano.dsa import (CATEGORIES, PriceAVLTree, UndoHistory, make_key,
                           plan_within_budget, sort_by_price)
from mealplano.tree_drawing import layout as tree_layout
from mealplano.validation import InputError, check_category, clean_name, normalize_name

UNDO_LIMIT = 20
MAX_TOTAL_ITEMS = 200            # 4 categories x 50 foods is plenty for one day's total
TRAVERSALS = ("inorder", "preorder", "postorder", "levelorder")


class _UserState:
    def __init__(self):
        # Each category's foods are ordered by (price, name): cheapest on the left.
        self.trees = {c: PriceAVLTree() for c in CATEGORIES}
        self.history = UndoHistory(limit=UNDO_LIMIT)


class FoodService:
    def __init__(self, db_path):
        self.db_path = db_path
        self._cache = {}                       # user_id -> _UserState
        self._lock = threading.RLock()

    # ---------- cache ----------

    def load_user(self, user_id):
        """Rebuild this user's four trees from SQLite (called on login)."""
        state = _UserState()
        for row in db.load_foods(self.db_path, user_id):     # insertion order
            state.trees[row["category"]].insert(row["display_name"], row["price_centavos"])
        with self._lock:
            self._cache[user_id] = state
        return state

    def logout(self, user_id):
        with self._lock:
            self._cache.pop(user_id, None)

    def _state(self, user_id):
        with self._lock:
            state = self._cache.get(user_id)
        return state if state is not None else self.load_user(user_id)

    def _find_all(self, state, name):
        """Search all four trees. Return [(category, node)] for every match, in category order.

        A name is unique within a category, so there are at most four matches.
        """
        matches = []
        for category in CATEGORIES:
            node = state.trees[category].search(name)
            if node is not None:
                matches.append((category, node))
        return matches

    def _find_in(self, state, category, name):
        """Search one category's tree; raise InputError if the food is not there."""
        node = state.trees[category].search(name)
        if node is None:
            raise InputError(f'"{name}" is not in {category}.')
        return node

    # ---------- changes ----------

    def add_food(self, user_id, category, name, price):
        """FR-2. Reject a name already in THIS category. Returns (category, name, price).

        The same name may be in other categories, even at a different price
        (e.g. Tapsilog in Breakfast and in Dinner).
        """
        category = check_category(category)
        name = clean_name(name)
        with self._lock:
            state = self._state(user_id)
            node = state.trees[category].search(name)
            if node is not None:
                raise InputError(f'"{node.display_name}" is already in {category}.')
            db.insert_food(self.db_path, user_id, category, make_key(name), name, price)
            state.trees[category].insert(name, price)
            state.history.record_add(category, name)
            return category, name, price

    def delete_food(self, user_id, category, name):
        """FR-4. Returns (category, display_name, price) of the removed food."""
        category = check_category(category)
        name = clean_name(name)
        with self._lock:
            state = self._state(user_id)
            node = self._find_in(state, category, name)
            key = node.name_key                  # read before delete: the node may be reused
            db.delete_food(self.db_path, user_id, category, key)
            display, price = state.trees[category].delete(key)
            state.history.record_delete(category, display, price)
            return category, display, price

    def update_price(self, user_id, category, name, new_price):
        """FR-8. Returns (category, display_name, old_price, new_price)."""
        category = check_category(category)
        name = clean_name(name)
        with self._lock:
            state = self._state(user_id)
            node = self._find_in(state, category, name)
            key, display = node.name_key, node.display_name     # read first: the food moves
            db.update_food_price(self.db_path, user_id, category, key, new_price)
            old = state.trees[category].update(key, new_price)
            state.history.record_update(category, display, old)
            return category, display, old, new_price

    def undo(self, user_id):
        """FR-18. Reverse the latest change. Returns (action, category, name, price) or None."""
        with self._lock:
            state = self._state(user_id)
            entry = state.history.peek()
            if entry is None:
                return None
            action, category, name, price = entry
            key = make_key(name)
            if action == "delete":
                db.delete_food(self.db_path, user_id, category, key)
            elif action == "add":
                db.insert_food(self.db_path, user_id, category, key, name, price)
            else:
                db.update_food_price(self.db_path, user_id, category, key, price)
            return state.history.undo(state.trees)

    def undo_count(self, user_id):
        return len(self._state(user_id).history)

    # ---------- reads (trees only, no SQL) ----------

    def find(self, user_id, name):
        """FR-3. Every match as [(category, display_name, price)], in category order.

        An empty list means "not found". Four O(log n) tree searches.
        """
        return [(category, node.display_name, node.price)
                for category, node in self._find_all(self._state(user_id), clean_name(name))]

    def menu(self, user_id, category):
        """FR-5. A category's foods, cheapest first (in-order traversal): [(display_name, price)]."""
        tree = self._state(user_id).trees[check_category(category)]
        return [(n.display_name, n.price) for n in tree.inorder()]

    def counts(self, user_id):
        state = self._state(user_id)
        return {c: len(state.trees[c]) for c in CATEGORIES}

    def traversal(self, user_id, category, order):
        """FR-7. Foods of one category in the chosen traversal order, plus the tree height."""
        if order not in TRAVERSALS:
            raise InputError("Choose in-order, pre-order, post-order, or level-order.")
        tree = self._state(user_id).trees[check_category(category)]
        nodes = getattr(tree, order)()
        return [(n.display_name, n.price) for n in nodes], tree.height()

    def tree_drawing(self, user_id, category, order):
        """Stretch goal: layout data for drawing a category's tree (or None if empty).

        Nodes are numbered in the visit order of the chosen traversal.
        """
        if order not in TRAVERSALS:
            raise InputError("Choose in-order, pre-order, post-order, or level-order.")
        tree = self._state(user_id).trees[check_category(category)]
        visit_order = [n.key for n in getattr(tree, order)()]
        return tree_layout(tree, visit_order)

    def sort_by_price(self, user_id, categories):
        """FR-16. Cheapest first: list of (category, display_name, price)."""
        categories = [check_category(c) for c in categories]
        if not categories:
            raise InputError("Choose at least one category.")
        return sort_by_price(self._state(user_id).trees, categories)

    def meal_total(self, user_id, picks=(), typed=()):
        """FR-6. Find each selected food by tree search and add the prices in centavos.

        picks  = [(category, name)]  foods ticked on the page: searched in that category
        typed  = [name]              names typed by hand: searched in all four categories

        Returns (found, missing, ambiguous, total):
          found      [(category, name, price)]
          missing    names not on the menu
          ambiguous  [(name, [categories])] typed names found in several
                     categories; they are not added, the user must tick one
        """
        picks = [(c, n) for c, n in ((c, normalize_name(n)) for c, n in picks) if n]
        typed = [n for n in (normalize_name(raw) for raw in typed) if n]
        if len(picks) + len(typed) > MAX_TOTAL_ITEMS:
            raise InputError(f"Choose at most {MAX_TOTAL_ITEMS} foods at a time.")
        if not picks and not typed:
            raise InputError("Enter at least one food name.")
        state = self._state(user_id)
        found, missing, ambiguous = [], [], []
        for category, name in picks:
            node = state.trees[category].search(name) if category in CATEGORIES else None
            if node is None:
                missing.append(name)
            else:
                found.append((category, node.display_name, node.price))
        for name in typed:
            matches = self._find_all(state, name)
            if not matches:
                missing.append(name)
            elif len(matches) > 1:
                ambiguous.append((matches[0][1].display_name, [c for c, _ in matches]))
            else:
                category, node = matches[0]
                found.append((category, node.display_name, node.price))
        return found, missing, ambiguous, sum(price for _, _, price in found)

    def budget(self, user_id, categories, budget_centavos):
        """FR-17. Best plan within the budget: one food per chosen category, total as
        close to the budget as possible without going over."""
        categories = [check_category(c) for c in categories]
        return plan_within_budget(self._state(user_id).trees, categories, budget_centavos)
