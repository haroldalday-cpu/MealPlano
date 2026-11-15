"""Keeps each user's trees and SQLite in sync, and owns the in-memory cache (PRD Section 11).

Rules:
  - A change (add, delete, update, undo) is validated, written to SQLite FIRST,
    then applied to the tree, then its inverse is pushed onto the undo stack.
    If the SQLite write fails, the tree is never touched.
  - A read (search, menu, sort, total, budget, tree view, calendar) uses the trees only.
  - The meal calendar follows the same rule: SQLite first, then the date tree.
    It is not on the undo stack; a planned meal is removed with its own button.
  - A user's trees are rebuilt from SQLite on login, or on first use after a
    server restart. Logout drops them and the undo history.

The cache lives in one Python process, so the app runs with a single worker
(local demo only). A lock stops two requests changing the same cache at once.
"""

import calendar as _calendar
import threading
from datetime import date

from mealplano import db
from mealplano.dsa import (CATEGORIES, BudgetError, DateAVLTree, PriceAVLTree, UndoHistory,
                           make_key, plan_within_budget, sort_by_price)
from mealplano.tree_drawing import layout as tree_layout
from mealplano.validation import InputError, check_category, clean_name, normalize_name

UNDO_LIMIT = 20
MAX_TOTAL_ITEMS = 200            # 4 categories x 50 foods is plenty for one day's total
TRAVERSALS = ("inorder", "preorder", "postorder", "levelorder")
WEEK_STARTS_ON = _calendar.SUNDAY         # like most wall calendars in the Philippines


class _UserState:
    def __init__(self):
        # Each category's foods are ordered by (price, name): cheapest on the left.
        self.trees = {c: PriceAVLTree() for c in CATEGORIES}
        self.history = UndoHistory(limit=UNDO_LIMIT)
        # Meal calendar: planned days ordered by date, and the (daily, weekly, monthly) budgets.
        self.calendar = DateAVLTree()
        self.goals = (None, None, None)


class FoodService:
    def __init__(self, db_path):
        self.db_path = db_path
        self._cache = {}                       # user_id -> _UserState
        self._lock = threading.RLock()

    # ---------- cache ----------

    def load_user(self, user_id):
        """Rebuild this user's four trees from SQLite (called on login)."""
        state = _UserState()
        for row in db.load_foods(self.db_path, user_id):     # insertion order
            state.trees[row["category"]].insert(row["display_name"], row["price_centavos"])
        for row in db.load_plans(self.db_path, user_id):
            state.calendar.set_meal(date.fromisoformat(row["plan_date"]), row["category"],
                                    row["display_name"], row["price_centavos"])
        state.goals = db.get_goals(self.db_path, user_id)
        with self._lock:
            self._cache[user_id] = state
        return state

    def logout(self, user_id):
        with self._lock:
            self._cache.pop(user_id, None)

    def _state(self, user_id):
        with self._lock:
            state = self._cache.get(user_id)
        return state if state is not None else self.load_user(user_id)

    def _find_all(self, state, name):
        """Search all four trees. Return [(category, node)] for every match, in category order.

        A name is unique within a category, so there are at most four matches.
        """
        matches = []
        for category in CATEGORIES:
            node = state.trees[category].search(name)
            if node is not None:
                matches.append((category, node))
        return matches

    def _find_in(self, state, category, name):
        """Search one category's tree; raise InputError if the food is not there."""
        node = state.trees[category].search(name)
        if node is None:
            raise InputError(f'"{name}" is not in {category}.')
        return node

    # ---------- changes ----------

    def add_food(self, user_id, category, name, price):
        """FR-2. Reject a name already in THIS category. Returns (category, name, price).

        The same name may be in other categories, even at a different price
        (e.g. Tapsilog in Breakfast and in Dinner).
        """
        category = check_category(category)
        name = clean_name(name)
        with self._lock:
            state = self._state(user_id)
            node = state.trees[category].search(name)
            if node is not None:
                raise InputError(f'"{node.display_name}" is already in {category}.')
            db.insert_food(self.db_path, user_id, category, make_key(name), name, price)
            state.trees[category].insert(name, price)
            state.history.record_add(category, name)
            return category, name, price

    def delete_food(self, user_id, category, name):
        """FR-4. Returns (category, display_name, price) of the removed food."""
        category = check_category(category)
        name = clean_name(name)
        with self._lock:
            state = self._state(user_id)
            node = self._find_in(state, category, name)
            key = node.name_key                  # read before delete: the node may be reused
            db.delete_food(self.db_path, user_id, category, key)
            display, price = state.trees[category].delete(key)
            state.history.record_delete(category, display, price)
            return category, display, price

    def update_price(self, user_id, category, name, new_price):
        """FR-8. Returns (category, display_name, old_price, new_price)."""
        category = check_category(category)
        name = clean_name(name)
        with self._lock:
            state = self._state(user_id)
            node = self._find_in(state, category, name)
            key, display = node.name_key, node.display_name     # read first: the food moves
            db.update_food_price(self.db_path, user_id, category, key, new_price)
            old = state.trees[category].update(key, new_price)
            state.history.record_update(category, display, old)
            return category, display, old, new_price

    def undo(self, user_id):
        """FR-18. Reverse the latest change. Returns (action, category, name, price) or None."""
        with self._lock:
            state = self._state(user_id)
            entry = state.history.peek()
            if entry is None:
                return None
            action, category, name, price = entry
            key = make_key(name)
            if action == "delete":
                db.delete_food(self.db_path, user_id, category, key)
            elif action == "add":
                db.insert_food(self.db_path, user_id, category, key, name, price)
            else:
                db.update_food_price(self.db_path, user_id, category, key, price)
            return state.history.undo(state.trees)

    def undo_count(self, user_id):
        return len(self._state(user_id).history)

    # ---------- reads (trees only, no SQL) ----------

    def find(self, user_id, name):
        """FR-3. Every match as [(category, display_name, price)], in category order.

        An empty list means "not found". Four O(log n) tree searches.
        """
        return [(category, node.display_name, node.price)
                for category, node in self._find_all(self._state(user_id), clean_name(name))]

    def menu(self, user_id, category):
        """FR-5. A category's foods, cheapest first (in-order traversal): [(display_name, price)]."""
        tree = self._state(user_id).trees[check_category(category)]
        return [(n.display_name, n.price) for n in tree.inorder()]

    def counts(self, user_id):
        state = self._state(user_id)
        return {c: len(state.trees[c]) for c in CATEGORIES}

    def traversal(self, user_id, category, order):
        """FR-7. Foods of one category in the chosen traversal order, plus the tree height."""
        if order not in TRAVERSALS:
            raise InputError("Choose in-order, pre-order, post-order, or level-order.")
        tree = self._state(user_id).trees[check_category(category)]
        nodes = getattr(tree, order)()
        return [(n.display_name, n.price) for n in nodes], tree.height()

    def tree_drawing(self, user_id, category, order):
        """Stretch goal: layout data for drawing a category's tree (or None if empty).

        Nodes are numbered in the visit order of the chosen traversal.
        """
        if order not in TRAVERSALS:
            raise InputError("Choose in-order, pre-order, post-order, or level-order.")
        tree = self._state(user_id).trees[check_category(category)]
        visit_order = [n.key for n in getattr(tree, order)()]
        return tree_layout(tree, visit_order)

    def sort_by_price(self, user_id, categories):
        """FR-16. Cheapest first: list of (category, display_name, price)."""
        categories = [check_category(c) for c in categories]
        if not categories:
            raise InputError("Choose at least one category.")
        return sort_by_price(self._state(user_id).trees, categories)

    def meal_total(self, user_id, picks=(), typed=()):
        """FR-6. Find each selected food by tree search and add the prices in centavos.

        picks  = [(category, name)]  foods ticked on the page: searched in that category
        typed  = [name]              names typed by hand: searched in all four categories

        Returns (found, missing, ambiguous, total):
          found      [(category, name, price)]
          missing    names not on the menu
          ambiguous  [(name, [categories])] typed names found in several
                     categories; they are not added, the user must tick one
        """
        picks = [(c, n) for c, n in ((c, normalize_name(n)) for c, n in picks) if n]
        typed = [n for n in (normalize_name(raw) for raw in typed) if n]
        if len(picks) + len(typed) > MAX_TOTAL_ITEMS:
            raise InputError(f"Choose at most {MAX_TOTAL_ITEMS} foods at a time.")
        if not picks and not typed:
            raise InputError("Enter at least one food name.")
        state = self._state(user_id)
        found, missing, ambiguous = [], [], []
        for category, name in picks:
            node = state.trees[category].search(name) if category in CATEGORIES else None
            if node is None:
                missing.append(name)
            else:
                found.append((category, node.display_name, node.price))
        for name in typed:
            matches = self._find_all(state, name)
            if not matches:
                missing.append(name)
            elif len(matches) > 1:
                ambiguous.append((matches[0][1].display_name, [c for c, _ in matches]))
            else:
                category, node = matches[0]
                found.append((category, node.display_name, node.price))
        return found, missing, ambiguous, sum(price for _, _, price in found)

    def budget(self, user_id, categories, budget_centavos):
        """FR-17. Best plan within the budget: one food per chosen category, total as
        close to the budget as possible without going over."""
        categories = [check_category(c) for c in categories]
        return plan_within_budget(self._state(user_id).trees, categories, budget_centavos)

    # ---------- meal calendar ----------

    def _save_day(self, user_id, state, day, meals):
        """meals = [(category, display_name, price)]: SQLite first (one transaction), then the tree."""
        db.upsert_plans(self.db_path, user_id, day.isoformat(), meals)
        for category, name, price in meals:
            state.calendar.set_meal(day, category, name, price)

    def plan_meal(self, user_id, day, category, name):
        """Plan one food for one category on a day, copying its current price.

        Replaces whatever was planned for that category. Returns (category, name, price).
        """
        category = check_category(category)
        name = clean_name(name)
        with self._lock:
            state = self._state(user_id)
            node = self._find_in(state, category, name)
            meal = (category, node.display_name, node.price)
            self._save_day(user_id, state, day, [meal])
            return meal

    def unplan_meal(self, user_id, day, category):
        """Remove one planned meal. Returns the removed (display_name, price)."""
        category = check_category(category)
        with self._lock:
            state = self._state(user_id)
            node = state.calendar.get(day)
            if node is None or category not in node.meals:
                raise InputError(f"Nothing is planned for {category} on {day:%d %b %Y}.")
            db.delete_plan(self.db_path, user_id, day.isoformat(), category)
            return state.calendar.remove_meal(day, category)

    def save_budget_plan(self, user_id, day, picks):
        """Save a budget planner result to a day. picks = [(category, name)].

        Prices are read from the trees again, never from the form. Every pick
        must still be on the menu, or nothing is saved. Returns the saved meals.
        """
        picks = [(check_category(c), clean_name(n)) for c, n in picks]
        if not picks:
            raise InputError("There is no plan to save.")
        if len({c for c, _ in picks}) != len(picks):
            raise InputError("A day can have only one food per category.")
        with self._lock:
            state = self._state(user_id)
            meals = []
            for category, name in picks:
                node = self._find_in(state, category, name)
                meals.append((category, node.display_name, node.price))
            self._save_day(user_id, state, day, meals)
            return meals

    def autoplan_day(self, user_id, day, budget_centavos):
        """Fill the day's empty categories with the best plan within the budget (FR-17's planner).

        Categories with no foods on the menu are skipped. Returns the plan dict
        from plan_within_budget; the meals are saved only if the plan fits.
        """
        with self._lock:
            state = self._state(user_id)
            node = state.calendar.get(day)
            planned = node.meals if node is not None else {}
            empty = [c for c in CATEGORIES if c not in planned]
            if not empty:
                raise InputError("Every category is already planned for this day.")
            empty = [c for c in empty if len(state.trees[c])]
            if not empty:
                raise InputError("The empty categories have no foods on your menu yet.")
            try:
                plan = plan_within_budget(state.trees, empty, budget_centavos)
            except BudgetError as err:
                raise InputError(str(err)) from None
            if plan["fits"]:
                self._save_day(user_id, state, day, plan["picks"])
            return plan

    def set_goals(self, user_id, daily, weekly, monthly):
        """Save the calendar budgets in centavos (None = not set)."""
        with self._lock:
            state = self._state(user_id)
            db.set_goals(self.db_path, user_id, daily, weekly, monthly)
            state.goals = (daily, weekly, monthly)

    def goals(self, user_id):
        return self._state(user_id).goals

    def month_view(self, user_id, year, month):
        """Everything the month grid needs. Totals come from the date tree's range query.

        weeks: [{"days": [cell x 7], "total", "over"}]; each cell is
               {"date", "in_month", "total", "count", "over"}.
        A week's total covers all 7 days, even the ones in the next or previous month.
        """
        state = self._state(user_id)
        daily, weekly, monthly = state.goals
        cal = _calendar.Calendar(firstweekday=WEEK_STARTS_ON)
        weeks = []
        for dates in cal.monthdatescalendar(year, month):
            planned = {n.day: n for n in state.calendar.range(dates[0], dates[-1])}
            cells = []
            for d in dates:
                node = planned.get(d)
                total = node.total() if node else 0
                cells.append({"date": d, "in_month": d.month == month, "total": total,
                              "count": len(node.meals) if node else 0,
                              "over": daily is not None and total > daily})
            week_total = state.calendar.range_total(dates[0], dates[-1])
            weeks.append({"days": cells, "total": week_total,
                          "over": weekly is not None and week_total > weekly})
        first = date(year, month, 1)
        last = date(year, month, _calendar.monthrange(year, month)[1])
        in_month = state.calendar.range(first, last)
        month_total = sum(n.total() for n in in_month)
        return {"year": year, "month": month, "first": first, "weeks": weeks,
                "total": month_total, "planned_days": len(in_month),
                "over": monthly is not None and month_total > monthly,
                "goals": {"daily": daily, "weekly": weekly, "monthly": monthly}}

    def day_view(self, user_id, day):
        """One day: its planned meals, the menus to pick from, and its total."""
        state = self._state(user_id)
        node = state.calendar.get(day)
        meals = dict(node.meals) if node else {}
        total = node.total() if node else 0
        daily = state.goals[0]
        menus = {c: [(n.display_name, n.price) for n in state.trees[c].inorder()]
                 for c in CATEGORIES}
        return {"date": day, "meals": meals, "total": total, "daily": daily,
                "over": daily is not None and total > daily,
                "left": daily - total if daily is not None else None,
                "menus": menus}
