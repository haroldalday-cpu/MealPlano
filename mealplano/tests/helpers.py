"""Invariant checker used after every tree change (PRD Section 10)."""

from mealplano.dsa.avl import AVLTree


def check_tree(tree):
    """Raise AssertionError unless the tree is a valid BST (and, for AVL, balanced).

    Checks:
      1. in-order output is strictly sorted by key (so ordering holds, no duplicates)
      2. the node count matches len(tree)
      3. AVL only: every stored height is correct
      4. AVL only: every balance factor is -1, 0, or 1
    """
    nodes = tree.inorder()
    keys = [n.key for n in nodes]
    for a, b in zip(keys, keys[1:]):
        assert a < b, f"in-order not sorted: {a!r} comes before {b!r}"
    assert len(nodes) == len(tree), f"size is {len(tree)} but tree holds {len(nodes)} nodes"

    if isinstance(tree, AVLTree):
        _check_avl(tree.root)


def shape(tree):
    """Snapshot of the tree's structure: pre-order keys with None for empty links.

    Two trees with equal snapshots have exactly the same shape and keys.
    Uses a loop, so it is safe on a degenerate 1,000-node BST.
    """
    out = []
    pending = [tree.root]
    while pending:
        node = pending.pop()
        if node is None:
            out.append(None)
            continue
        out.append(node.key)
        pending.append(node.right)
        pending.append(node.left)
    return out


def _check_avl(node):
    """Return the true height of this subtree, asserting AVL rules on the way."""
    if node is None:
        return 0
    left = _check_avl(node.left)
    right = _check_avl(node.right)
    true_height = 1 + max(left, right)
    assert node.height == true_height, (
        f"{node.display_name!r} stores height {node.height}, real height is {true_height}"
    )
    assert abs(left - right) <= 1, (
        f"{node.display_name!r} has balance factor {left - right}"
    )
    return true_height
