"""Merge Sort and Quick Sort (PRD Section 8, concept 6) and sort-by-price (FR-16).

Both sorts take a list and a `key` function and return a NEW sorted list;
the input is not changed.

Merge Sort: O(n log n) in every case, and STABLE (items with equal keys keep
their original order). This is the one the app uses.

Quick Sort: last-element pivot (Lomuto partition), kept for the comparison.
O(n log n) on average, but O(n^2) on already-sorted input, because the pivot
is always the largest item and one side of every split is empty. To avoid a
RecursionError there, it recurses only into the SMALLER side and loops over
the larger one, so recursion depth stays at most log2(n).
"""


def merge_sort(items, key=lambda x: x):
    items = list(items)
    if len(items) <= 1:
        return items
    mid = len(items) // 2
    left = merge_sort(items[:mid], key)
    right = merge_sort(items[mid:], key)
    return _merge(left, right, key)


def _merge(left, right, key):
    merged = []
    i = j = 0
    while i < len(left) and j < len(right):
        # "<=" takes from the left half on a tie: this is what makes it stable.
        if key(left[i]) <= key(right[j]):
            merged.append(left[i])
            i += 1
        else:
            merged.append(right[j])
            j += 1
    merged.extend(left[i:])
    merged.extend(right[j:])
    return merged


def quick_sort(items, key=lambda x: x):
    items = list(items)
    keys = [key(x) for x in items]      # compute each key once
    _quick_sort(items, keys, 0, len(items) - 1)
    return items


def _quick_sort(items, keys, low, high):
    while low < high:
        p = _partition(items, keys, low, high)
        # Recurse into the smaller part, then loop on the larger part.
        if p - low < high - p:
            _quick_sort(items, keys, low, p - 1)
            low = p + 1
        else:
            _quick_sort(items, keys, p + 1, high)
            high = p - 1


def _partition(items, keys, low, high):
    """Lomuto partition around items[high]. Return the pivot's final index."""
    pivot = keys[high]
    i = low - 1
    for j in range(low, high):
        if keys[j] <= pivot:
            i += 1
            items[i], items[j] = items[j], items[i]
            keys[i], keys[j] = keys[j], keys[i]
    items[i + 1], items[high] = items[high], items[i + 1]
    keys[i + 1], keys[high] = keys[high], keys[i + 1]
    return i + 1


def sort_by_price(trees, categories):
    """FR-16: foods from the chosen categories, cheapest first.

    `trees` is a dict: category -> tree. Returns a list of
    (category, display_name, price) tuples. Equal prices stay in alphabetical
    order because Merge Sort is stable and is given an alphabetical list:
    the foods are first merge-sorted by name, then by price.

    With the app's price-ordered trees, one category's in-order traversal is
    already cheapest first, so Merge Sort finds it sorted (its best case).
    Sorting is still needed to merge several categories into one list.
    """
    rows = []
    for category in categories:
        rows.extend((category, n.display_name, n.price, n.name_key) for n in trees[category].inorder())
    rows = merge_sort(rows, key=lambda r: r[3])              # alphabetical first
    rows = merge_sort(rows, key=lambda r: r[2])              # then by price, stable
    return [(category, name, price) for category, name, price, _ in rows]
