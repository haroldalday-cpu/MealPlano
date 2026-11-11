"""Budget planner (FR-17): the best plan within the budget.

Goal: one food from each chosen category, with the total as CLOSE TO THE
BUDGET AS POSSIBLE WITHOUT GOING OVER ("what is the best I can eat for P200?").

Why greedy is not enough: the best food to take in one category depends on
how much budget the other categories leave. This is a small version of the
knapsack problem (exactly one item from each group).

Why not try every plan: 50 foods in each of 4 categories is 50**4 = 6.25
million plans.

Method: MEET IN THE MIDDLE.
  1. Split the chosen categories into two halves (at most 2 categories each).
  2. For each half, list every subtotal it can make, dropping subtotals that
     are already over budget and keeping one plan per distinct subtotal.
  3. Sort both subtotal lists with Merge Sort.
  4. Two pointers: walk one list upward and the other downward to find the
     largest left + right that is still <= budget. O(a + b) after sorting.
  With n foods per category that is O(n^2 log n) instead of O(n^4).

The greedy CHEAPEST plan (one leftmost node per price tree) is still computed
first: if even the cheapest plan is over budget, no plan fits, and the
planner reports by how much.

exhaustive_best() tries every combination. It exists only so the tests can
confirm meet in the middle finds the same total on small menus.
"""

from itertools import product

from .node import validate_price
from .sorting import merge_sort


class BudgetError(ValueError):
    """Raised for an invalid budget, no categories, or an empty category."""


def cheapest_food(tree):
    """The cheapest food as (display_name, price); on a price tie the alphabetically first.

    A price-ordered tree (the app's PriceAVLTree) has it as its leftmost node:
    O(log n). Any other tree (e.g. the name-ordered AVLTree) needs one in-order
    pass: O(n).
    """
    leftmost = getattr(tree, "cheapest", None)
    if leftmost is not None:
        node = leftmost()
        return None if node is None else (node.display_name, node.price)
    best = None
    for node in tree.inorder():
        if best is None or node.price < best[1]:      # strict "<" keeps the first on ties
            best = (node.display_name, node.price)
    return best


def _subtotals(trees, categories, budget):
    """Every subtotal <= budget that one food per category can make.

    Returns {subtotal: picks}, picks = ((category, name, price), ...), keeping
    the first plan found for each subtotal. Foods are tried cheapest first, so
    the loop can stop as soon as a price pushes the subtotal over budget.
    """
    sums = {0: ()}
    for category in categories:
        foods = merge_sort([(n.display_name, n.price) for n in trees[category].inorder()],
                           key=lambda f: f[1])           # already sorted for price trees
        grown = {}
        for subtotal, picks in sums.items():
            for name, price in foods:
                total = subtotal + price
                if total > budget:
                    break                                 # every later food costs more
                if total not in grown:
                    grown[total] = picks + ((category, name, price),)
        sums = grown
    return sums


def _best_pair(left, right, budget):
    """Largest a + b <= budget with a in left and b in right (both sorted ascending).

    Two pointers: i walks left upward, j walks right downward. Returns
    (a, b), or None if no pair fits.
    """
    best, best_pair = -1, None
    j = len(right) - 1
    for a in left:
        while j >= 0 and a + right[j] > budget:
            j -= 1                                        # a only grows, so j never moves back up
        if j < 0:
            break
        if a + right[j] > best:
            best, best_pair = a + right[j], (a, right[j])
            if best == budget:
                break                                     # cannot do better than exact
    return best_pair


def plan_within_budget(trees, categories, budget_centavos):
    """The best plan with one food per chosen category, without going over the budget.

    Result dict:
      picks           [(category, display_name, price)] in the order the categories were given
      total           sum of the picked prices, in centavos
      fits            False if even the cheapest plan is over budget
      remaining       budget - total when it fits, else 0
      shortfall       cheapest total - budget when nothing fits, else 0
      cheapest_total  the cheapest possible plan's total (greedy), for comparison
    When nothing fits, picks is the cheapest plan, so the user sees what is closest.
    """
    try:
        validate_price(budget_centavos)
    except ValueError:
        raise BudgetError("Budget must be a positive amount.") from None
    if not categories:
        raise BudgetError("Choose at least one category.")

    # Greedy first: the cheapest plan is a lower bound and a quick "does anything fit?".
    cheapest = []
    for category in categories:
        food = cheapest_food(trees[category])
        if food is None:
            raise BudgetError(f"{category} has no foods yet.")
        cheapest.append((category, food[0], food[1]))
    cheapest_total = sum(price for _, _, price in cheapest)

    if cheapest_total > budget_centavos:
        return {"picks": cheapest, "total": cheapest_total, "fits": False, "remaining": 0,
                "shortfall": cheapest_total - budget_centavos, "cheapest_total": cheapest_total}

    # Meet in the middle.
    half = len(categories) // 2
    left = _subtotals(trees, categories[:half], budget_centavos)
    right = _subtotals(trees, categories[half:], budget_centavos)
    a, b = _best_pair(merge_sort(list(left)), merge_sort(list(right)), budget_centavos)

    by_category = {c: (c, name, price) for c, name, price in left[a] + right[b]}
    picks = [by_category[c] for c in categories]
    total = a + b
    return {"picks": picks, "total": total, "fits": True,
            "remaining": budget_centavos - total, "shortfall": 0,
            "cheapest_total": cheapest_total}


def exhaustive_best(trees, categories, budget_centavos):
    """Try every combination; return the largest total <= budget, or None. For testing only."""
    menus = [[n.price for n in trees[c].inorder()] for c in categories]
    fitting = [sum(combo) for combo in product(*menus) if sum(combo) <= budget_centavos]
    return max(fitting) if fitting else None
