"""Comparison A (PRD Section 9): finding a food by name.

Approaches: linear search on an unsorted list, binary search on a sorted array,
plain BST, AVL tree. Each is measured at several sizes, with foods inserted in
random order and in alphabetical order (the plain BST's worst case).

Measured per (approach, order, n):
  insert_s   time to insert all n foods (median of 5 builds)
  search_us  average time per lookup over 1,000 lookups, half present and
             half absent (median of 5 rounds), in microseconds
  height     final tree height (trees only)

Run from the project folder:
    python -m mealplano.benchmarks.bench_lookup            # full run, a few minutes
    python -m mealplano.benchmarks.bench_lookup --quick    # small sizes, 1 run, for checking
"""

import argparse
import math
import random

from mealplano.benchmarks.common import (RESULTS, RUNS, SEED, line_chart, markdown_table,
                                         median_time, write_csv)
from mealplano.dsa import BST, AVLTree
from mealplano.dsa.searching import binary_search, linear_search, sorted_insert

FULL_SIZES = [100, 1_000, 10_000, 50_000]
QUICK_SIZES = [100, 1_000]
BST_SORTED_CAP = 10_000      # O(n^2) build: alphabetical input to a plain BST
LOOKUPS = 1_000


# ---- the four approaches, each with build() and lookup() ----

class UnsortedList:
    label = "Linear search (unsorted list)"
    is_tree = False

    def __init__(self):
        self.items = []

    def insert(self, key, price):
        # Append only, O(1), as in PRD Section 9's table. Rejecting duplicates
        # would need a linear scan first, making insert O(n); the app's
        # duplicate check (FR-2) is not part of this measurement.
        self.items.append((key, price))

    def lookup(self, key):
        return linear_search(self.items, key)


class SortedArray:
    label = "Binary search (sorted array)"
    is_tree = False

    def __init__(self):
        self.items = []

    def insert(self, key, price):
        sorted_insert(self.items, key, price)

    def lookup(self, key):
        return binary_search(self.items, key)


class _TreeApproach:
    is_tree = True
    tree_class = None

    def __init__(self):
        self.tree = self.tree_class()

    def insert(self, key, price):
        self.tree.insert(key, price)

    def lookup(self, key):
        node = self.tree.search(key)
        return node.price if node is not None else None

    def height(self):
        return self.tree.height()


class PlainBST(_TreeApproach):
    label = "Plain BST"
    tree_class = BST


class AVL(_TreeApproach):
    label = "AVL tree"
    tree_class = AVLTree


APPROACHES = [UnsortedList, SortedArray, PlainBST, AVL]


# ---- test data ----

def make_foods(n, order, rng):
    """n unique (key, price) pairs, in random or alphabetical order."""
    keys = [f"food{i:06d}" for i in range(n)]
    foods = [(k, rng.randint(1, 10_000_000)) for k in keys]
    if order == "random":
        rng.shuffle(foods)
    return foods                              # keys were generated already sorted


def make_lookups(foods, rng):
    """1,000 lookups: half present names, half absent, shuffled together."""
    present = [k for k, _ in rng.sample(foods, min(LOOKUPS // 2, len(foods)))]
    # "food000123~" is never a real name, and it sorts right next to a real
    # one, so absent searches go just as deep as present ones.
    absent = [k + "~" for k, _ in rng.choices(foods, k=LOOKUPS - len(present))]
    lookups = present + absent
    rng.shuffle(lookups)
    return lookups


def build(approach, foods):
    s = approach()
    for key, price in foods:
        s.insert(key, price)
    return s


# ---- the benchmark ----

def run(sizes, runs):
    rows = []
    for order in ["random", "alphabetical"]:
        for n in sizes:
            rng = random.Random(SEED + n)     # same data for every approach at this n
            foods = make_foods(n, order, rng)
            lookups = make_lookups(foods, rng)
            truth = dict(foods)
            expected = [truth.get(k) for k in lookups]

            for approach in APPROACHES:
                if approach is PlainBST and order == "alphabetical" and n > BST_SORTED_CAP:
                    print(f"  skip  {approach.label:32} {order:12} n={n:>6}  (O(n^2) cap)")
                    continue

                structure = build(approach, foods)
                # Correctness first: a fast wrong answer does not count.
                got = [structure.lookup(k) for k in lookups]
                if got != expected:
                    raise AssertionError(f"{approach.label} returned wrong results at n={n}, {order}")

                insert_s = median_time(lambda: build(approach, foods), runs)
                search_s = median_time(lambda: [structure.lookup(k) for k in lookups], runs)
                row = {
                    "approach": approach.label,
                    "order": order,
                    "n": n,
                    "insert_s": round(insert_s, 6),
                    "search_us": round(search_s / len(lookups) * 1e6, 3),
                    "height": structure.height() if approach.is_tree else "",
                }
                rows.append(row)
                print(f"  done  {approach.label:32} {order:12} n={n:>6}  "
                      f"insert {row['insert_s']:>10.4f} s   search {row['search_us']:>9.3f} us"
                      + (f"   height {row['height']}" if row["height"] != "" else ""))
    return rows


def charts(rows, sizes):
    def series(order, field):
        return {a.label: [(r["n"], r[field]) for r in rows
                          if r["approach"] == a.label and r["order"] == order]
                for a in APPROACHES}

    paths = []
    for order in ["random", "alphabetical"]:
        paths.append(line_chart(f"lookup_search_{order}.png",
                                f"Average search time, {order} insert order",
                                "microseconds per search (log scale)",
                                series(order, "search_us")))
        paths.append(line_chart(f"lookup_insert_{order}.png",
                                f"Time to insert all n foods, {order} order",
                                "seconds (log scale)",
                                series(order, "insert_s")))

    heights = {}
    for a in (PlainBST, AVL):
        for order in ["random", "alphabetical"]:
            heights[f"{a.label}, {order}"] = [(r["n"], r["height"]) for r in rows
                                              if r["approach"] == a.label and r["order"] == order]
    heights["log2(n+1), the best possible"] = [(n, math.log2(n + 1)) for n in sizes]
    heights["1.44 log2(n+1), AVL bound"] = [(n, 1.44 * math.log2(n + 1)) for n in sizes]
    paths.append(line_chart("tree_height.png", "Final tree height", "height (log scale)", heights))
    return paths


def summary(rows):
    cols = ["approach", "order", "n", "insert_s", "search_us", "height"]
    text = ["# Comparison A: lookup benchmark results", "",
            f"Seed {SEED}, median of {RUNS} runs, {LOOKUPS} lookups per round "
            "(half present, half absent).",
            f"Plain BST with alphabetical input is capped at n = {BST_SORTED_CAP:,} "
            "because building it is O(n^2).", "",
            markdown_table(rows, cols), ""]
    path = RESULTS / "lookup_summary.md"
    path.write_text("\n".join(text), encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="small sizes and 1 run, for a fast check")
    args = parser.parse_args()
    sizes, runs = (QUICK_SIZES, 1) if args.quick else (FULL_SIZES, RUNS)

    print(f"Comparison A: lookup, sizes {sizes}, {runs} run(s) each")
    rows = run(sizes, runs)
    csv_path = write_csv("lookup.csv" if not args.quick else "lookup_quick.csv", rows)
    if args.quick:
        print(f"Quick check passed. Wrote {csv_path}")
        return
    for p in [csv_path, summary(rows), *charts(rows, sizes)]:
        print(f"Wrote {p}")


if __name__ == "__main__":
    main()
