# MealPLANO

A web-based meal planner and budget tracker built on **AVL-balanced binary search trees**.
Each user's foods live in four trees, one per meal category (Breakfast, Lunch, Dinner, Snacks),
**ordered by price**: cheapest on the left. A meal calendar plans days ahead, stored in a fifth
AVL tree **ordered by date**. DSA Final Project, 2026.

## How the trees are ordered

Each category tree (`mealplano/dsa/price_tree.py`) is keyed by **(price, name)**: cheaper foods go
left, and foods with the same price are ordered alphabetically, so every key is unique.

| Operation | Cost | Why |
|---|---|---|
| Menu, cheapest first | O(n) | In-order traversal; no sorting step |
| Cheapest food (budget planner's first check) | O(log n) | The leftmost node |
| Find a food by name (search, duplicate check, delete, price update) | O(n) | The tree is ordered by price, not name, so it is walked |
| Insert, delete once found | O(log n) | AVL insert/delete with rotations |
| Price update | O(n) find + O(log n) | The price is part of the key, so the food is deleted and re-inserted: it **moves** |

The meal calendar (`mealplano/dsa/date_tree.py`) is a separate AVL tree keyed by **date**; each
node is one planned day with at most one food per category.

| Operation | Cost | Why |
|---|---|---|
| Open a day, plan or remove a meal | O(log n) | AVL search, insert, delete (n = planned days) |
| Week or month total | O(log n + k) | Range query: an in-order walk that skips subtrees outside the dates (k = days in range) |

The lookup benchmark (report Section 5, Comparison A) keys every structure the same way, by
(price, name), and uses ascending prices (cheapest first) as the plain BST's worst case. The
name-ordered `BST` and `AVLTree` classes are still in the `dsa` package; the benchmark's trees are
small subclasses of them with the price key.

## Quick start

Requires Python 3.12 or newer (developed on Python 3.14.5, Windows 11).

```bash
python -m pip install -r requirements.txt
python -m mealplano.seed_demo                  # optional: demo account with 24 Filipino dishes and 10 planned days
python -m flask --app mealplano.app run
```

Open http://127.0.0.1:5000 and register, or log in with the demo account:

| Username | Password |
|---|---|
| `demo` | `mealplano-demo` |

The demo account is for the local demo only. `seed_demo` can be run again at any time to reset its
menu and calendar. The calendar is planned for the 10 days **starting on the day you run it**, so run
it on the morning of the defense.

## Running the tests and benchmarks

```bash
python -m unittest discover -s mealplano/tests -t . -v      # 278 tests
python -m coverage run --source=mealplano --omit="mealplano/tests/*,mealplano/benchmarks/*" -m unittest discover -s mealplano/tests -t .
python -m coverage report                                    # 99% line coverage
python -m mealplano.benchmarks.bench_lookup                  # Comparison A, a few minutes
python -m mealplano.benchmarks.bench_sort                    # Comparison B
```

Benchmark results (CSV, summary tables, and charts) are written to `mealplano/benchmarks/results/`.

## DSA concepts and where they are

| # | Concept | File | Used for |
|---|---|---|---|
| 1 | Binary search tree | `mealplano/dsa/bst.py` | Baseline in the lookup benchmark |
| 2 | AVL tree | `mealplano/dsa/avl.py`, `mealplano/dsa/price_tree.py` | Stores every category's foods in the app, ordered by (price, name) |
| 3 | Tree traversals (in, pre, post, level) | `mealplano/dsa/bst.py` | Cheapest-first menu, tree view |
| 4 | Queue (hand-built, linked) | `mealplano/dsa/linked_queue.py` | Level-order traversal |
| 5 | Stack (hand-built, linked) | `mealplano/dsa/stack.py` | Undo, last 20 changes |
| 6 | Merge Sort and Quick Sort | `mealplano/dsa/sorting.py` | Sort by price (Merge Sort); Quick Sort for comparison |
| 7 | Meet in the middle + two pointers (with a greedy first check) | `mealplano/dsa/budget.py` | Best day plan within a budget: as close to the budget as possible without going over |
| 8 | AVL tree keyed by date + range query (iterative, with the linked stack) | `mealplano/dsa/date_tree.py` | Meal calendar: days, week and month totals |
| – | Linear and binary search | `mealplano/dsa/searching.py` | Alternatives in the lookup benchmark |

The `dsa` package has no Flask or SQL imports and can be tested and benchmarked on its own.

## Requirements and where they are met

| ID | Feature | Code | Page |
|---|---|---|---|
| FR-1 | Category selection | `food_service.py` | Menu tabs |
| FR-2 | Add food; a name is unique within its category (the same food may be in several categories, even at different prices) | `food_service.add_food` | Menu |
| FR-3 | Search all four trees; lists every category the food is in | `food_service.find` | Search |
| FR-4 | Delete (leaf, one child, two children) | `price_tree.delete` (uses `avl._delete`) | Menu |
| FR-5 | Menu, cheapest first | `bst.inorder` on the price tree | Menu |
| FR-6 | Meal total, exact in centavos | `food_service.meal_total` | Meal total |
| FR-7 | Tree view: a drawing of the tree (stretch goal) plus the visit-order list | `bst.preorder/postorder/levelorder`, `tree_drawing.py` | Tree view |
| FR-8 | Price update; the food moves to its new price position | `price_tree.update` | Menu |
| FR-9 to FR-11 | Register, login, logout, salted password hashes | `auth.py`, `app.py` | Login, Register |
| FR-12 | Each user sees only their own foods | every query and cache entry keyed by user id | all |
| FR-13 | Accounts survive restarts | `db.py` (SQLite) | – |
| FR-14 | Food pages need login | `app.login_required` | all |
| FR-16 | Sort by price | `sorting.merge_sort` | Sort by price |
| FR-17 | Budget planner: best plan within the budget (one food per category, closest to the budget without going over) | `budget.plan_within_budget` | Budget planner |
| FR-18 | Undo, 20 steps | `stack.UndoHistory` | Menu (Undo button) |
| FR-19 | AVL balancing | `avl._rebalance` | – |
| FR-20 | Foods survive restarts, trees rebuilt on login | `food_service.load_user` | – |
| FR-21 | Meal calendar: plan days ahead by hand or by saving a budget plan; prices are copied when planned; daily, weekly and monthly budgets with over-budget warnings | `date_tree.DateAVLTree`, `food_service.plan_meal` / `save_budget_plan` / `autoplan_day` / `month_view` | Calendar, Budget planner (Save to calendar) |

FR-15 (change password, delete account) was a "Could" item and is not built.
The tree drawing (stretch goal) is built: each box shows the food, its price, its AVL balance
factor, and its visit number in the chosen traversal. Only the top 4 levels are drawn; deeper
branches are shown as "+k" counts.

## How it fits together

```
browser ──HTTP──> app.py / food_routes.py   (validation, sessions, CSRF)
                        │
                  food_service.py           (one cache entry per logged-in user)
                   │            │
   write first ──> db.py        dsa/ ── four AVL trees + undo stack per user
                (SQLite file)   (all reads are answered from the trees)
```

* A change is validated, written to SQLite **first**, then applied to the tree, then its inverse is pushed onto the undo stack. If the database write fails, the tree is not touched.
* On login the user's foods are loaded `ORDER BY id` (insertion order) and inserted into four new AVL trees, and their planned meals into the date tree.
* Calendar changes follow the same SQLite-first rule. They are not on the undo stack; a planned meal has its own Remove button.
* The cache lives in one Python process, so the app runs with a single worker. It is a local demo, not a public deployment.

## Data and files

| Path | What it is |
|---|---|
| `instance/mealplano.db` | SQLite database: `users`, `foods`, `meal_plans` and `budget_goals` tables. Open it with `python -m sqlite3 instance/mealplano.db`. |
| `instance/secret_key` | Random key that signs login cookies. Created on first run. Do not share or submit it. |
| `BUG_LOG.md` | Every bug found, its cause, fix, and the test that now guards it. |
| `mealplano/benchmarks/results/` | Benchmark CSVs, summaries, and charts used in report Section 5. |

## Look and feel

The site is styled like a cheerful cooking game: a striped shop awning, a wooden counter, order
tickets with "EXACT!" / "FITS!" / "OVER" stamps and a 0-3 star score on the budget planner, a chef
mascot whose face follows the result, and small animations (new foods slide in with a "+₱80.50"
popup).

* **All art is original**, drawn for this project as inline SVG in `mealplano/templates/_art.html`
  and coloured in `static/style.css`. No images, fonts, sounds or characters from any game or
  other third party are used.
* Pure CSS, no extra JavaScript, so the Content-Security-Policy is unchanged; the tests check
  every page for inline styles and inline scripts.
* Every animation is switched off when the operating system's "reduce motion" setting is on.

## Security measures

* Passwords stored only as salted scrypt hashes (werkzeug); a generic login error; constant-ish time for unknown usernames.
* Parameterised SQL only; every food query is scoped to the logged-in user's id.
* CSRF token on every form; logout is a POST; after login only local `next` pages are followed.
* Signed, HTTP-only, SameSite=Lax session cookie; secret key kept outside the code.
* Security headers (CSP, X-Frame-Options, nosniff); logged-in pages are sent with `Cache-Control: no-store`.
* Input rules from PRD Section 12: names 1–50 printable characters (inner spaces collapsed), prices ₱0.01 to ₱100,000.00 with at most 2 decimals, requests over 64 KB rejected. Bad input shows a message and never a crash.

## Demo walkthrough (about 8 minutes)

Run `python -m mealplano.seed_demo` and start the server before the defense. Each step names what to say.

1. **Log in** as `demo`. *"Login rebuilt four AVL trees from SQLite in insertion order."*
2. **Menu → Lunch.** *"The trees are keyed by price, so in-order traversal lists the menu cheapest first with no sorting: Pancit Canton ₱65, then Bicol Express and Tinola at ₱75, alphabetical on the tie."*
3. **Add** `adobo` to Lunch. *"Rejected: a name is unique within its category's tree, ignoring case. That is exactly what a BST needs."* Then add `Adobo`, ₱90, to Dinner: accepted, because Dinner is a separate tree. **Search** `adobo`: it lists Lunch ₱80.50 and Dinner ₱90.00. Then add `Laing na Gabi`, ₱70, to Dinner.
4. **Tree view → Dinner, pre-order**: Bistek Tagalog (₱90) is numbered 1, so it is the root. **Change** the Lunch Adobo's price to `85.50` (*"the price is part of the key, so Adobo moves: delete and re-insert"*), then **delete** Bistek Tagalog. *"The root has two children, the hardest delete case: its in-order successor, the next price up, takes its place and the tree rebalances."*
5. **Undo** twice. *"The stack pops the inverse of each change: Bistek Tagalog is back at ₱90.00, then Adobo is back at ₱80.50."*
6. **Tree view → Dinner**, switch through the four orders and watch the orange numbers move around the drawing. *"Pre-order numbers the root first, post-order last, level-order goes row by row using our linked queue. Every balance factor is -1, 0 or +1, so the height stays near log₂ n."*
7. **Sort by price**, all categories. *"Each tree is already in price order; Merge Sort combines the four lists. It is stable, so Banana Cue and Turon at ₱20 stay alphabetical."*
8. **Meal total**: tick Tapsilog, Adobo (Lunch), Turon. *"Each tick names its category, so it is one search in one tree; prices are summed in centavos, so the total is exact."* Typing `adobo` instead shows that it is in two categories and asks you to tick one.
9. **Budget planner**: ₱200 for all four categories. The plan is Taho ₱25, Pancit Canton ₱65, Menudo ₱85, Kwek-Kwek ₱25 = exactly ₱200 ("Uses your budget exactly"); the cheapest possible plan would be ₱165. Then try ₱100: no plan fits, ₱65.00 short. *"First a greedy check: the cheapest plan is each tree's leftmost node, so if even that is over budget, nothing fits. Otherwise, meet in the middle: split the categories into two halves, list every subtotal each half can make, Merge Sort both lists, and match them with two pointers. That is O(n² log n) instead of trying all n⁴ plans, and the tests check it against exhaustive search on 400 random menus."*
10. **Calendar.** *"Planned days live in a fifth AVL tree, keyed by date."* The month shows the planned days, and the days over the ₱200 daily budget are orange; so is the week with the fiesta day (₱440), over ₱1,300. Then:
    * Open tomorrow and **Remove** its Snacks.
    * Use **Fill the empty slots** with ₱20: the budget planner picks a snack that fits.
    * Go back to the Budget planner, run ₱200 again, and click **Save to calendar** for a date next week.
    * Change Adobo's price on the Menu. The planned days keep their old price, because a calendar day is a record of the plan.

    *"A week or month total is a range query: walk the tree in order, but skip any subtree that is entirely before the first date or after the last one. That is O(log n + k)."*
11. **Restart the server**, log in again: everything is still there (FR-20).
12. **Benchmarks:** show `lookup_search_ascending.png` and `sort_sorted.png`. *"Adding foods cheapest first makes the plain BST 195× slower than AVL at 10,000 foods; sorted input makes Quick Sort 290× slower than Merge Sort."*

Likely panel questions, with the short answer:

* *Why order the trees by price, not name?* A meal planner on a budget mostly asks price questions: cheapest-first menus and the cheapest food per category come straight from the tree. The trade-off is that finding a food by name is O(n), because the tree is not ordered by name. For one person's menu (tens of foods per category) that is not noticeable; the tests check pages stay under 1 second with 500 foods per category.
* *Why not greedy for the budget planner?* Greedy is right for the cheapest plan, but not for the best plan within a budget: the best food in one category depends on how much the other categories leave. It is a small knapsack problem (exactly one item per group). With at most 4 categories, meet in the middle splits it into two halves of at most 2 categories, so it stays fast: 200 foods per category (1.6 billion plans) is solved well under a second.
* *Why is the key (price, name) and not just price?* Prices repeat (₱20 Turon and ₱20 Banana Cue), and BST keys must be unique. The name breaks ties.
* *Why not a Python dict?* A dict gives O(1) lookup but no order; the menu, tree view and budget planner all need price order, and the course asks for the tree.
* *Why may the same food be in two categories?* Each category is its own tree, and a BST only needs unique keys within one tree. It also lets a dish cost more at dinner than at breakfast. The database enforces it with `UNIQUE (user_id, category, key)`.
* *Why both SQLite and trees?* SQLite keeps data across restarts; the trees do the work. Reads never touch SQL.
* *What happens on a crash between the SQLite write and the tree update?* The tree is rebuilt from SQLite on the next login, so SQLite is the source of truth.
* *Why a tree for the calendar and not a dict of dates?* A dict finds one date in O(1) but cannot list a week or month in order without sorting every key. The date tree's range query visits only the days in range, already in date order.
* *Why copy the price into the plan?* A planned day is a record: if the menu price changes or the food is deleted, last week's spending should not change.
* *Why is undo limited to 20 and lost on logout?* It is a per-session convenience, capped so memory stays bounded; the stack drops its oldest entry in O(1).
