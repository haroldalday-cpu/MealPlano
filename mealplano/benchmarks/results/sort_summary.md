# Comparison B: sorting benchmark results

Seed 42, median of 5 runs. Quick Sort uses a last-element pivot.
Quick Sort on sorted and duplicate-heavy input is capped at n = 10,000 because it is O(n^2) there.

| algorithm | input | n | time_s |
|---|---|---|---|
| Merge Sort | random | 1000 | 0.001362 |
| Quick Sort | random | 1000 | 0.000907 |
| Merge Sort | random | 10000 | 0.019952 |
| Quick Sort | random | 10000 | 0.01067 |
| Merge Sort | random | 100000 | 0.243017 |
| Quick Sort | random | 100000 | 0.143567 |
| Merge Sort | sorted | 1000 | 0.001024 |
| Quick Sort | sorted | 1000 | 0.035057 |
| Merge Sort | sorted | 10000 | 0.013002 |
| Quick Sort | sorted | 10000 | 3.775162 |
| Merge Sort | sorted | 100000 | 0.159904 |
| Merge Sort | duplicates | 1000 | 0.001446 |
| Quick Sort | duplicates | 1000 | 0.002471 |
| Merge Sort | duplicates | 10000 | 0.020027 |
| Quick Sort | duplicates | 10000 | 0.194579 |
| Merge Sort | duplicates | 100000 | 0.231668 |
