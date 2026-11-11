"""Plain binary search tree: the baseline for the lookup benchmark.

Every method is a loop, not recursion. A plain BST fed alphabetical input
becomes a chain of n nodes, and recursion that deep would hit Python's
default limit of 1,000 calls (PRD Section 10, "Likely bugs").
"""

from .linked_queue import LinkedQueue
from .node import FoodNode, make_key, validate_price


class BST:
    def __init__(self):
        self.root = None
        self.size = 0

    def __len__(self):
        return self.size

    def insert(self, display_name, price_centavos):
        """Insert a food. Return False if the name is already in this tree."""
        new = FoodNode(display_name, price_centavos)
        if self.root is None:
            self.root = new
            self.size = 1
            return True

        current = self.root
        while True:
            if new.key == current.key:
                return False
            if new.key < current.key:
                if current.left is None:
                    current.left = new
                    break
                current = current.left
            else:
                if current.right is None:
                    current.right = new
                    break
                current = current.right
        self.size += 1
        return True

    def search(self, name):
        """Return the node for this name, or None if it is not in the tree."""
        key = make_key(name)
        current = self.root
        while current is not None:
            if key == current.key:
                return current
            current = current.left if key < current.key else current.right
        return None

    def update(self, name, new_price_centavos):
        """Change a food's price in place (FR-8). Return the old price, or None if missing.

        The key does not change, so the node stays where it is: O(height), no reshaping.
        """
        validate_price(new_price_centavos)
        node = self.search(name)
        if node is None:
            return None
        old_price = node.price
        node.price = new_price_centavos
        return old_price

    def delete(self, name):
        """Remove a food (FR-4). Return (display_name, price) of what was removed, or None.

        Three cases:
          leaf          -> just unlink it
          one child     -> the child takes its place
          two children  -> copy in the in-order successor (smallest key in the
                           right subtree), then remove the successor, which has
                           no left child so it is always case 1 or 2
        """
        key = make_key(name)
        parent = None
        node = self.root
        while node is not None and node.key != key:
            parent = node
            node = node.left if key < node.key else node.right
        if node is None:
            return None

        removed = (node.display_name, node.price)

        if node.left is not None and node.right is not None:
            # Two children: find the successor and its parent.
            succ_parent = node
            succ = node.right
            while succ.left is not None:
                succ_parent = succ
                succ = succ.left
            node.key, node.name_key = succ.key, succ.name_key
            node.display_name, node.price = succ.display_name, succ.price
            # Now remove the successor node instead (it has at most a right child).
            parent, node = succ_parent, succ

        # node has at most one child here.
        child = node.left if node.left is not None else node.right
        if parent is None:
            self.root = child
        elif parent.left is node:
            parent.left = child
        else:
            parent.right = child

        self.size -= 1
        return removed

    def inorder(self):
        """Return all nodes in alphabetical order (left, node, right)."""
        result = []
        pending = []          # nodes whose left side is done but who are not yet visited
        current = self.root
        while current is not None or pending:
            while current is not None:
                pending.append(current)
                current = current.left
            current = pending.pop()
            result.append(current)
            current = current.right
        return result

    def preorder(self):
        """Node, then left subtree, then right subtree (FR-7)."""
        result = []
        pending = [self.root] if self.root is not None else []
        while pending:
            node = pending.pop()
            result.append(node)
            # Push right first so left is popped (visited) first.
            if node.right is not None:
                pending.append(node.right)
            if node.left is not None:
                pending.append(node.left)
        return result

    def postorder(self):
        """Left subtree, then right subtree, then node (FR-7).

        Visit in node-right-left order, then reverse: reversed, that is
        exactly left-right-node.
        """
        result = []
        pending = [self.root] if self.root is not None else []
        while pending:
            node = pending.pop()
            result.append(node)
            if node.left is not None:
                pending.append(node.left)
            if node.right is not None:
                pending.append(node.right)
        result.reverse()
        return result

    def levelorder(self):
        """Top level first, left to right within a level (FR-7), using LinkedQueue."""
        result = []
        if self.root is None:
            return result
        queue = LinkedQueue()
        queue.enqueue(self.root)
        while not queue.is_empty():
            node = queue.dequeue()
            result.append(node)
            if node.left is not None:
                queue.enqueue(node.left)
            if node.right is not None:
                queue.enqueue(node.right)
        return result

    def height(self):
        """Number of nodes on the longest root-to-leaf path (0 for an empty tree)."""
        if self.root is None:
            return 0
        tallest = 0
        pending = [(self.root, 1)]
        while pending:
            node, depth = pending.pop()
            tallest = max(tallest, depth)
            if node.left is not None:
                pending.append((node.left, depth + 1))
            if node.right is not None:
                pending.append((node.right, depth + 1))
        return tallest
