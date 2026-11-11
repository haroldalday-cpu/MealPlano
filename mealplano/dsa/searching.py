"""List-based lookups used as the alternatives in Comparison A (PRD Section 9).

Each list holds (key, price) tuples. The searches are plain Python loops, not
`in` or `bisect`, so they run at the same speed level as the tree code and
the comparison is fair.
"""


def linear_search(items, key):
    """Unsorted list: check every item. O(n). Return the price or None."""
    for item_key, price in items:
        if item_key == key:
            return price
    return None


def _lower_bound(items, key):
    """Index of the first item whose key is >= key (binary search loop)."""
    low, high = 0, len(items)
    while low < high:
        mid = (low + high) // 2
        if items[mid][0] < key:
            low = mid + 1
        else:
            high = mid
    return low


def binary_search(items, key):
    """Sorted list: halve the range each step. O(log n). Return the price or None."""
    i = _lower_bound(items, key)
    if i < len(items) and items[i][0] == key:
        return items[i][1]
    return None


def sorted_insert(items, key, price):
    """Insert into a sorted list, keeping it sorted. Return False on a duplicate.

    Finding the spot is O(log n), but list.insert must shift every later item
    one place to the right, so the insert as a whole is O(n).
    """
    i = _lower_bound(items, key)
    if i < len(items) and items[i][0] == key:
        return False
    items.insert(i, (key, price))
    return True
