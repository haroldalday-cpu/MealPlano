# Comparison A: lookup benchmark results

Seed 42, median of 5 runs, 1000 lookups per round (half present, half absent).
Plain BST with alphabetical input is capped at n = 10,000 because building it is O(n^2).

| approach | order | n | insert_s | search_us | height |
|---|---|---|---|---|---|
| Linear search (unsorted list) | random | 100 | 7e-06 | 1.917 |  |
| Binary search (sorted array) | random | 100 | 7.4e-05 | 0.647 |  |
| Plain BST | random | 100 | 7.8e-05 | 0.503 | 14 |
| AVL tree | random | 100 | 0.000233 | 0.453 | 8 |
| Linear search (unsorted list) | random | 1000 | 6.1e-05 | 15.144 |  |
| Binary search (sorted array) | random | 1000 | 0.000849 | 0.86 |  |
| Plain BST | random | 1000 | 0.001182 | 0.834 | 26 |
| AVL tree | random | 1000 | 0.003022 | 0.544 | 12 |
| Linear search (unsorted list) | random | 10000 | 0.000934 | 144.784 |  |
| Binary search (sorted array) | random | 10000 | 0.01612 | 1.16 |  |
| Plain BST | random | 10000 | 0.013767 | 0.866 | 29 |
| AVL tree | random | 10000 | 0.042657 | 0.749 | 16 |
| Linear search (unsorted list) | random | 50000 | 0.00668 | 843.685 |  |
| Binary search (sorted array) | random | 50000 | 0.226956 | 2.029 |  |
| Plain BST | random | 50000 | 0.10746 | 1.297 | 42 |
| AVL tree | random | 50000 | 0.299286 | 1.174 | 19 |
| Linear search (unsorted list) | alphabetical | 100 | 7e-06 | 1.737 |  |
| Binary search (sorted array) | alphabetical | 100 | 4.6e-05 | 0.54 |  |
| Plain BST | alphabetical | 100 | 0.000277 | 2.018 | 100 |
| AVL tree | alphabetical | 100 | 0.000216 | 0.421 | 7 |
| Linear search (unsorted list) | alphabetical | 1000 | 6.1e-05 | 14.411 |  |
| Binary search (sorted array) | alphabetical | 1000 | 0.000829 | 0.897 |  |
| Plain BST | alphabetical | 1000 | 0.027669 | 18.845 | 1000 |
| AVL tree | alphabetical | 1000 | 0.003141 | 0.539 | 10 |
| Linear search (unsorted list) | alphabetical | 10000 | 0.000674 | 138.388 |  |
| Binary search (sorted array) | alphabetical | 10000 | 0.011017 | 1.152 |  |
| Plain BST | alphabetical | 10000 | 2.634237 | 210.166 | 10000 |
| AVL tree | alphabetical | 10000 | 0.044482 | 0.799 | 14 |
| Linear search (unsorted list) | alphabetical | 50000 | 0.00444 | 911.684 |  |
| Binary search (sorted array) | alphabetical | 50000 | 0.066503 | 2.731 |  |
| AVL tree | alphabetical | 50000 | 0.267108 | 0.995 | 16 |
