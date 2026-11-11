"""Comparison B (PRD Section 9): sorting foods by price.

Merge Sort vs. Quick Sort (last-element pivot) on three kinds of input:
  random      random prices
  sorted      prices already in order (Quick Sort's worst case)
  duplicates  only 20 distinct prices, so most prices repeat

Quick Sort on sorted and duplicate-heavy input is O(n^2), so those cases are
capped at n = 10,000 (PRD Section 9).

Run from the project folder:
    python -m mealplano.benchmarks.bench_sort            # full run
    python -m mealplano.benchmarks.bench_sort --quick    # small sizes, 1 run
"""

import argparse
import random

from mealplano.benchmarks.common import (RESULTS, RUNS, SEED, line_chart, markdown_table,
                                         median_time, write_csv)
from mealplano.dsa import merge_sort, quick_sort

FULL_SIZES = [1_000, 10_000, 100_000]
QUICK_SIZES = [1_000, 5_000]
QUICK_SORT_CAP = 10_000
INPUTS = ["random", "sorted", "duplicates"]
ALGORITHMS = {"Merge Sort": merge_sort, "Quick Sort": quick_sort}


def make_prices(n, kind, rng):
    if kind == "duplicates":
        return [rng.randint(1, 20) * 500 for _ in range(n)]        # P5, P10, ... P100
    prices = [rng.randint(1, 10_000_000) for _ in range(n)]
    return sorted(prices) if kind == "sorted" else prices


def run(sizes, runs):
    rows = []
    for kind in INPUTS:
        for n in sizes:
            prices = make_prices(n, kind, random.Random(SEED + n))
            expected = sorted(prices)
            for name, sort in ALGORITHMS.items():
                if name == "Quick Sort" and kind != "random" and n > QUICK_SORT_CAP:
                    print(f"  skip  {name:10} {kind:10} n={n:>7}  (O(n^2) cap)")
                    continue
                if sort(prices) != expected:
                    raise AssertionError(f"{name} gave a wrong result at n={n}, {kind}")
                seconds = median_time(lambda: sort(prices), runs)
                rows.append({"algorithm": name, "input": kind, "n": n, "time_s": round(seconds, 6)})
                print(f"  done  {name:10} {kind:10} n={n:>7}  {seconds:>9.4f} s")
    return rows


def charts(rows):
    paths = []
    for kind in INPUTS:
        series = {name: [(r["n"], r["time_s"]) for r in rows
                         if r["algorithm"] == name and r["input"] == kind]
                  for name in ALGORITHMS}
        paths.append(line_chart(f"sort_{kind}.png", f"Sorting time, {kind} prices",
                                "seconds (log scale)", series))
    return paths


def summary(rows):
    text = ["# Comparison B: sorting benchmark results", "",
            f"Seed {SEED}, median of {RUNS} runs. Quick Sort uses a last-element pivot.",
            f"Quick Sort on sorted and duplicate-heavy input is capped at n = {QUICK_SORT_CAP:,} "
            "because it is O(n^2) there.", "",
            markdown_table(rows, ["algorithm", "input", "n", "time_s"]), ""]
    path = RESULTS / "sort_summary.md"
    path.write_text("\n".join(text), encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--quick", action="store_true", help="small sizes and 1 run, for a fast check")
    args = parser.parse_args()
    sizes, runs = (QUICK_SIZES, 1) if args.quick else (FULL_SIZES, RUNS)

    print(f"Comparison B: sorting, sizes {sizes}, {runs} run(s) each")
    rows = run(sizes, runs)
    csv_path = write_csv("sort.csv" if not args.quick else "sort_quick.csv", rows)
    if args.quick:
        print(f"Quick check passed. Wrote {csv_path}")
        return
    for p in [csv_path, summary(rows), *charts(rows)]:
        print(f"Wrote {p}")


if __name__ == "__main__":
    main()
