"""AVL tree: the category store used by the app (FR-19).

Same interface as BST. After every insert, each node on the path back to the
root updates its height and, if its balance factor reaches -2 or +2, is fixed
with one of four rotations (LL, RR, LR, RL). That keeps the height at most
about 1.44 * log2(n), so recursion depth stays small and is safe here.
"""

from .bst import BST
from .node import FoodNode, make_key


def _height(node):
    return node.height if node is not None else 0


def _update_height(node):
    node.height = 1 + max(_height(node.left), _height(node.right))


def balance_factor(node):
    """Left height minus right height."""
    return _height(node.left) - _height(node.right)


def _rotate_right(top):
    #       top             new_top
    #      /               /      \
    #   new_top    ->    ...      top
    #       \                    /
    #     middle              middle
    new_top = top.left
    middle = new_top.right
    new_top.right = top
    top.left = middle
    _update_height(top)
    _update_height(new_top)
    return new_top


def _rotate_left(top):
    new_top = top.right
    middle = new_top.left
    new_top.left = top
    top.right = middle
    _update_height(top)
    _update_height(new_top)
    return new_top


def _rebalance(node):
    """Fix one node whose children are already balanced. Return the subtree's new root."""
    _update_height(node)
    bf = balance_factor(node)

    if bf > 1:                                   # left side too tall
        if balance_factor(node.left) < 0:        # LR case: turn it into LL first
            node.left = _rotate_left(node.left)
        return _rotate_right(node)               # LL case

    if bf < -1:                                  # right side too tall
        if balance_factor(node.right) > 0:       # RL case: turn it into RR first
            node.right = _rotate_right(node.right)
        return _rotate_left(node)                # RR case

    return node


class AVLTree(BST):
    # search(), inorder() and update() are inherited from BST unchanged:
    # balancing changes the shape, not the ordering rule, and a price
    # update never moves a node.

    def insert(self, display_name, price_centavos):
        """Insert a food and rebalance. Return False if the name is already here."""
        new = FoodNode(display_name, price_centavos)
        self._inserted = False
        self.root = self._insert(self.root, new)
        if self._inserted:
            self.size += 1
        return self._inserted

    def _insert(self, node, new):
        if node is None:
            self._inserted = True
            return new
        if new.key == node.key:
            return node                          # duplicate: tree unchanged
        if new.key < node.key:
            node.left = self._insert(node.left, new)
        else:
            node.right = self._insert(node.right, new)
        return _rebalance(node)

    def delete(self, name):
        """Remove a food and rebalance. Return (display_name, price) removed, or None."""
        self._removed = None
        self.root = self._delete(self.root, make_key(name))
        if self._removed is not None:
            self.size -= 1
        return self._removed

    def _delete(self, node, key):
        if node is None:
            return None                          # key not in this subtree
        if key < node.key:
            node.left = self._delete(node.left, key)
        elif key > node.key:
            node.right = self._delete(node.right, key)
        else:
            if self._removed is None:            # record only the food the user asked for,
                self._removed = (node.display_name, node.price)   # not the successor below
            if node.left is None:                # leaf or right child only
                return node.right
            if node.right is None:               # left child only
                return node.left
            # Two children: copy in the in-order successor, then delete it
            # from the right subtree (rebalancing on the way back up).
            succ = node.right
            while succ.left is not None:
                succ = succ.left
            node.key, node.name_key = succ.key, succ.name_key
            node.display_name, node.price = succ.display_name, succ.price
            node.right = self._delete(node.right, succ.key)
        return _rebalance(node)

    def height(self):
        """Stored height of the root; O(1) because AVL keeps heights up to date."""
        return _height(self.root)
