"""Meal calendar: an AVL tree keyed by date, with a range query.

Each node is one planned day. Its key is the date's ordinal (days since
1 January of year 1), so earlier dates go left. A day holds at most one food
per category, stored as (display_name, price_centavos): the price is copied
when the meal is planned, so a later menu price change does not alter it.

Operations (n = planned days, k = days in the range):
  get, set_meal, remove_meal   O(log n)   AVL search, insert, delete
  range(start, end)            O(log n + k)
  range_total(start, end)      O(log n + k)

range() is an in-order walk that skips whole subtrees outside the bounds:
if a node is before `start`, nothing in its left subtree can be in range,
and if it is after `end`, nothing in its right subtree can be. It uses the
hand-built LinkedStack instead of recursion. Week and month totals on the
calendar page come from range_total().

The rotations are the same functions the food trees use (avl.py): they only
touch left, right and height, so they work on DayNode as well.
"""

from .avl import _height, _rebalance
from .stack import LinkedStack


class DayNode:
    __slots__ = ("key", "day", "meals", "left", "right", "height")

    def __init__(self, day):
        self.key = day.toordinal()
        self.day = day
        self.meals = {}                  # category -> (display_name, price_centavos)
        self.left = None
        self.right = None
        self.height = 1

    def total(self):
        return sum(price for _, price in self.meals.values())

    def __repr__(self):
        return f"DayNode({self.day.isoformat()}, {self.meals!r})"


class DateAVLTree:
    def __init__(self):
        self.root = None
        self.size = 0

    def __len__(self):
        return self.size

    def height(self):
        return _height(self.root)

    # ---------- search ----------

    def get(self, day):
        """The DayNode for this date, or None if nothing is planned."""
        key = day.toordinal()
        node = self.root
        while node is not None:
            if key == node.key:
                return node
            node = node.left if key < node.key else node.right
        return None

    def day_total(self, day):
        node = self.get(day)
        return node.total() if node is not None else 0

    # ---------- changes ----------

    def set_meal(self, day, category, display_name, price_centavos):
        """Plan (or replace) one category's food for a day. Return the old (name, price) or None."""
        node = self.get(day)
        if node is None:
            node = DayNode(day)
            self.root = self._insert(self.root, node)
            self.size += 1
        old = node.meals.get(category)
        node.meals[category] = (display_name, price_centavos)
        return old

    def remove_meal(self, day, category):
        """Remove one category's food from a day. Return the removed (name, price) or None.

        A day with no meals left is deleted from the tree.
        """
        node = self.get(day)
        if node is None or category not in node.meals:
            return None
        removed = node.meals.pop(category)
        if not node.meals:
            self.root = self._delete(self.root, node.key)
            self.size -= 1
        return removed

    def _insert(self, node, new):
        if node is None:
            return new
        if new.key < node.key:
            node.left = self._insert(node.left, new)
        else:                             # keys are unique: set_meal checks get() first
            node.right = self._insert(node.right, new)
        return _rebalance(node)

    def _delete(self, node, key):
        if node is None:
            return None
        if key < node.key:
            node.left = self._delete(node.left, key)
        elif key > node.key:
            node.right = self._delete(node.right, key)
        else:
            if node.left is None:
                return node.right
            if node.right is None:
                return node.left
            # Two children: copy in the in-order successor (the next date),
            # then delete the successor from the right subtree.
            succ = node.right
            while succ.left is not None:
                succ = succ.left
            node.key, node.day, node.meals = succ.key, succ.day, succ.meals
            node.right = self._delete(node.right, succ.key)
        return _rebalance(node)

    # ---------- range query ----------

    def range(self, start, end):
        """Planned days with start <= date <= end, earliest first."""
        lo, hi = start.toordinal(), end.toordinal()
        out = []
        if lo > hi:
            return out
        stack = LinkedStack()
        node = self.root
        while node is not None or not stack.is_empty():
            # Go left only while the left side can still hold dates >= start.
            while node is not None:
                if node.key < lo:
                    node = node.right          # this node and its left subtree are too early
                else:
                    stack.push(node)
                    node = node.left
            if stack.is_empty():
                break
            node = stack.pop()
            if node.key > hi:
                break                          # in-order: every later node is also too late
            out.append(node)
            node = node.right
        return out

    def range_total(self, start, end):
        return sum(node.total() for node in self.range(start, end))

    def inorder(self):
        """Every planned day, earliest first (used by tests)."""
        if self.root is None:
            return []
        lowest = self.root
        while lowest.left is not None:
            lowest = lowest.left
        highest = self.root
        while highest.right is not None:
            highest = highest.right
        return self.range(lowest.day, highest.day)
