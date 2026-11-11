"""Hand-built FIFO queue on a singly linked list (PRD Section 8, concept 4).

Why not a Python list? list.pop(0) shifts every remaining element, so each
dequeue is O(n). Here enqueue adds at the tail and dequeue removes at the
head, both O(1).
"""


class _QueueNode:
    __slots__ = ("value", "next")

    def __init__(self, value):
        self.value = value
        self.next = None


class LinkedQueue:
    def __init__(self):
        self._head = None     # front: next item to leave
        self._tail = None     # back: last item added
        self._size = 0

    def __len__(self):
        return self._size

    def is_empty(self):
        return self._size == 0

    def enqueue(self, value):
        node = _QueueNode(value)
        if self._tail is None:            # empty queue: node is both ends
            self._head = node
        else:
            self._tail.next = node
        self._tail = node
        self._size += 1

    def dequeue(self):
        if self._head is None:
            raise IndexError("dequeue from an empty queue")
        node = self._head
        self._head = node.next
        if self._head is None:            # queue became empty
            self._tail = None
        self._size -= 1
        return node.value

    def peek(self):
        if self._head is None:
            raise IndexError("peek at an empty queue")
        return self._head.value
