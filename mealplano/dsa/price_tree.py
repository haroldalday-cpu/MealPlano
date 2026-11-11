"""AVL tree ordered by PRICE: the category store used by the app.

Ordering key = (price, name_key): cheaper foods go left, and foods with the
same price are ordered alphabetically, so every key is unique.

Same interface as AVLTree (insert, search, delete, update, traversals); the
balancing code (rotations, rebalance on insert and delete) is inherited
unchanged, because it only compares keys.

What the price order changes:

  Operation                    Name-ordered AVLTree   PriceAVLTree
  ---------------------------  ---------------------  -------------------------------
  in-order traversal           alphabetical           cheapest first
  cheapest food                O(n) scan              O(log n): the leftmost node
  find by name (search)        O(log n)               O(n): the tree is not ordered
                                                      by name, so it is walked
  insert (with duplicate       O(log n)               O(n): name check, then
    name check)                                       O(log n) insert
  delete by name               O(log n)               O(n) find + O(log n) delete
  price update                 O(log n), node stays   O(n) find + O(log n) delete and
                                                      re-insert: the food MOVES
"""

from .avl import AVLTree
from .node import FoodNode, make_key, validate_price


class PriceAVLTree(AVLTree):

    @staticmethod
    def _new_node(display_name, price_centavos):
        node = FoodNode(display_name, price_centavos)
        node.key = (node.price, node.name_key)
        return node

    def insert(self, display_name, price_centavos):
        """Insert a food in price order. Return False if the NAME is already here.

        The same name at another price would have a different key, so names
        are checked separately (O(n)) before the O(log n) insert.
        """
        new = self._new_node(display_name, price_centavos)
        if self.search(new.name_key) is not None:
            return False
        self._inserted = False
        self.root = self._insert(self.root, new)       # inherited AVL insert + rebalance
        self.size += 1
        return True

    def search(self, name):
        """Find a food by NAME. O(n): walk the tree in order, stop at the first match."""
        key = make_key(name)
        pending = []
        current = self.root
        while current is not None or pending:
            while current is not None:
                pending.append(current)
                current = current.left
            current = pending.pop()
            if current.name_key == key:
                return current
            current = current.right
        return None

    def search_exact(self, price_centavos, name):
        """Find a food by its full ordering key (price, name). O(log n)."""
        key = (price_centavos, make_key(name))
        current = self.root
        while current is not None:
            if key == current.key:
                return current
            current = current.left if key < current.key else current.right
        return None

    def delete(self, name):
        """Remove a food by name. Return (display_name, price) removed, or None."""
        node = self.search(name)
        if node is None:
            return None
        self._removed = None
        self.root = self._delete(self.root, node.key)   # inherited AVL delete + rebalance
        self.size -= 1
        return self._removed

    def update(self, name, new_price_centavos):
        """Change a food's price. Return the old price, or None if the food is missing.

        The price is part of the key, so the food is deleted and re-inserted
        at its new position (unlike the name-ordered tree, where it stays put).
        """
        validate_price(new_price_centavos)
        node = self.search(name)
        if node is None:
            return None
        old_price, display = node.price, node.display_name
        if old_price != new_price_centavos:
            self.delete(node.name_key)
            self.insert(display, new_price_centavos)
        return old_price

    def cheapest(self):
        """The cheapest food (alphabetically first on a tie): the leftmost node. O(log n)."""
        current = self.root
        if current is None:
            return None
        while current.left is not None:
            current = current.left
        return current
