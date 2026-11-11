"""Lay out a category's AVL tree for the Tree view drawing (PRD stretch goal).

Layout rule (a common textbook one):
  x = the node's position in the in-order traversal, so the picture reads
      left to right in key order (cheapest first in the app's price-ordered
      trees) and no two nodes ever overlap;
  y = the node's depth.

Only the top MAX_LEVELS levels are drawn so a big menu stays readable
(static/tree.js then shrinks the picture to fit the page, down to 60%). A node
on the last drawn level with children below it gets a "+k" marker saying how
many foods are hidden under it on that side.

This module only READS the tree; it returns plain numbers and strings that
the template turns into SVG.
"""

MAX_LEVELS = 4      # up to 15 boxes: readable on a laptop screen
SLOT_W = 124        # horizontal space per in-order position
LEVEL_H = 100       # vertical space per level
BOX_W, BOX_H = 112, 58
MARGIN = 24
NAME_CHARS = 14     # longer names are shortened in the box; the full name is in the tooltip


def _height(node):
    return node.height if node is not None else 0


def _subtree_size(node):
    """Count the nodes under (and including) node, with a loop."""
    count, pending = 0, [node] if node is not None else []
    while pending:
        n = pending.pop()
        count += 1
        if n.left is not None:
            pending.append(n.left)
        if n.right is not None:
            pending.append(n.right)
    return count


def _short(name):
    return name if len(name) <= NAME_CHARS else name[:NAME_CHARS - 1] + "…"


def layout(tree, visit_order=(), max_levels=MAX_LEVELS):
    """Return a dict describing the drawing, or None for an empty tree.

    visit_order: node keys in the chosen traversal's order; each drawn node is
    labelled with its 1-based position in that order.
    """
    if tree.root is None:
        return None
    position = {key: i + 1 for i, key in enumerate(visit_order)}
    placed = []                   # in-order list of drawn nodes
    parent_of = {}

    def walk(node, depth, parent_key):
        # Recursion depth is at most max_levels (5), so this is always safe.
        if node is None:
            return
        last_level = depth == max_levels - 1
        if not last_level:
            walk(node.left, depth + 1, node.key)
        placed.append({
            "key": node.key,
            "name": node.display_name,
            "short": _short(node.display_name),
            "price": node.price,
            "depth": depth,
            "bf": _height(node.left) - _height(node.right),
            "height": node.height,
            "order": position.get(node.key),
            "hidden_left": _subtree_size(node.left) if last_level else 0,
            "hidden_right": _subtree_size(node.right) if last_level else 0,
        })
        parent_of[node.key] = parent_key
        if not last_level:
            walk(node.right, depth + 1, node.key)

    walk(tree.root, 0, None)

    for slot, item in enumerate(placed):
        item["x"] = MARGIN + slot * SLOT_W + SLOT_W // 2        # centre of the box
        item["y"] = MARGIN + item["depth"] * LEVEL_H            # top of the box
    by_key = {item["key"]: item for item in placed}

    edges = []
    for item in placed:
        parent = by_key.get(parent_of[item["key"]])
        if parent is not None:
            edges.append({"x1": parent["x"], "y1": parent["y"] + BOX_H,
                          "x2": item["x"], "y2": item["y"]})

    stubs = []                    # "+k" markers for hidden branches
    for item in placed:
        for side, count in (("left", item["hidden_left"]), ("right", item["hidden_right"])):
            if count:
                dx = -30 if side == "left" else 30
                stubs.append({"x1": item["x"] + dx // 2, "y1": item["y"] + BOX_H,
                              "x2": item["x"] + dx, "y2": item["y"] + BOX_H + 26,
                              "count": count, "side": side})

    levels_drawn = max(item["depth"] for item in placed) + 1
    total = len(tree)
    return {
        "root_x": by_key[tree.root.key]["x"],
        "nodes": placed,
        "edges": edges,
        "stubs": stubs,
        "width": MARGIN * 2 + len(placed) * SLOT_W,
        "height": MARGIN * 2 + (levels_drawn - 1) * LEVEL_H + BOX_H + (34 if stubs else 0),
        "box_w": BOX_W,
        "box_h": BOX_H,
        "shown": len(placed),
        "total": total,
        "levels_drawn": levels_drawn,
        "tree_height": tree.height(),
        "truncated": len(placed) < total,
    }
