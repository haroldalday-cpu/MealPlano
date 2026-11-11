"""Hand-built LIFO stack and the undo history built on it (PRD Section 8, concept 5).

LinkedStack: push and pop at the top in O(1). With a capacity, pushing onto a
full stack drops the OLDEST entry (the bottom), also O(1), because each node
links both up and down (a doubly linked list).

UndoHistory (FR-18): every change pushes its inverse.
    add food     -> push ("delete", category, name, None)
    delete food  -> push ("add",    category, name, old price)
    update price -> push ("update", category, name, old price)
undo() pops one entry and applies it to the right category tree. It returns
the entry it applied so the caller (the food service) can make the same
change in SQLite. Entries store names and prices, never node references:
a two-children delete reuses nodes, so a stored reference can go stale
(see BUG_LOG.md, 2026-11-07).
"""

from .node import make_key


class _StackNode:
    __slots__ = ("value", "below", "above")

    def __init__(self, value):
        self.value = value
        self.below = None
        self.above = None


class LinkedStack:
    def __init__(self, capacity=None):
        if capacity is not None and capacity < 1:
            raise ValueError("capacity must be at least 1")
        self.capacity = capacity
        self._top = None
        self._bottom = None
        self._size = 0

    def __len__(self):
        return self._size

    def is_empty(self):
        return self._size == 0

    def push(self, value):
        node = _StackNode(value)
        if self._top is None:
            self._bottom = node
        else:
            node.below = self._top
            self._top.above = node
        self._top = node
        self._size += 1
        if self.capacity is not None and self._size > self.capacity:
            self._drop_bottom()

    def pop(self):
        if self._top is None:
            raise IndexError("pop from an empty stack")
        node = self._top
        self._top = node.below
        if self._top is None:
            self._bottom = None
        else:
            self._top.above = None
        self._size -= 1
        return node.value

    def peek(self):
        if self._top is None:
            raise IndexError("peek at an empty stack")
        return self._top.value

    def clear(self):
        self._top = self._bottom = None
        self._size = 0

    def _drop_bottom(self):
        old = self._bottom
        self._bottom = old.above
        self._bottom.below = None
        self._size -= 1


class UndoHistory:
    def __init__(self, limit=20):
        self._stack = LinkedStack(capacity=limit)

    def __len__(self):
        return len(self._stack)

    def clear(self):
        """Called on logout (PRD Section 8)."""
        self._stack.clear()

    def record_add(self, category, display_name):
        self._stack.push(("delete", category, display_name, None))

    def record_delete(self, category, display_name, price):
        self._stack.push(("add", category, display_name, price))

    def record_update(self, category, display_name, old_price):
        self._stack.push(("update", category, display_name, old_price))

    def peek(self):
        """The entry undo() would apply next, without removing it (None if empty).

        Lets the caller write the change to SQLite first, then call undo().
        """
        return None if self._stack.is_empty() else self._stack.peek()

    def undo(self, trees):
        """Reverse the latest change in `trees` (a dict: category -> tree).

        Returns the (action, category, name, price) entry that was applied,
        or None when there is nothing to undo.
        """
        if self._stack.is_empty():
            return None
        entry = self._stack.pop()
        action, category, name, price = entry
        tree = trees[category]
        if action == "delete":
            tree.delete(make_key(name))
        elif action == "add":
            tree.insert(name, price)
        else:
            tree.update(name, price)
        return entry
