"""Shared helpers for the benchmark scripts: timing, CSV, and charts."""

import csv
import statistics
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")                     # draw to files, no window needed
import matplotlib.pyplot as plt          # noqa: E402

RESULTS = Path(__file__).resolve().parent / "results"
SEED = 42
RUNS = 5


def median_time(fn, runs=RUNS):
    """Run fn() `runs` times and return the median wall time in seconds.

    Only fn() is timed; any data it needs must be prepared before calling this.
    """
    times = []
    for _ in range(runs):
        start = time.perf_counter()
        fn()
        times.append(time.perf_counter() - start)
    return statistics.median(times)


def write_csv(name, rows):
    RESULTS.mkdir(exist_ok=True)
    path = RESULTS / name
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return path


def line_chart(filename, title, ylabel, series, log_y=True):
    """series: {label: [(n, value), ...]}. One line per approach, time vs n."""
    RESULTS.mkdir(exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    for label, points in series.items():
        if not points:
            continue
        xs, ys = zip(*points)
        ax.plot(xs, ys, marker="o", label=label)
    ax.set_xscale("log")
    if log_y:
        ax.set_yscale("log")
    ax.set_xlabel("n (number of foods)")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, which="both", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    path = RESULTS / filename
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def markdown_table(rows, columns):
    header = "| " + " | ".join(columns) + " |"
    rule = "|" + "---|" * len(columns)
    body = ["| " + " | ".join(str(r[c]) for c in columns) + " |" for r in rows]
    return "\n".join([header, rule, *body])
