"""Food pages (Milestone 7). Every route needs login and calls FoodService only.

Changes (add, delete, update, undo) are POST forms that redirect back to the
menu (post/redirect/get), so a browser refresh never repeats a change.
Reads (search, total, sort, budget, tree view, calendar pages) are GET forms.
Calendar changes (plan, remove, fill, budgets, save a budget plan) are POST forms too.
"""

from datetime import date, timedelta

from flask import flash, g, redirect, render_template, request, session, url_for

from mealplano.dsa import CATEGORIES
from mealplano.food_service import TRAVERSALS
from mealplano.validation import (InputError, date_window, format_pesos, parse_date, parse_month,
                                  parse_optional_pesos, parse_pesos)

ORDER_LABELS = {
    "inorder": "In-order (left, node, right): cheapest first",
    "preorder": "Pre-order (node, left, right)",
    "postorder": "Post-order (left, right, node)",
    "levelorder": "Level-order (top level first, using the linked queue)",
}


WEEKDAY_NAMES = ("Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat")


def plan_stars(plan, budget_centavos):
    """0 to 3 stars for a budget plan, like a cooking game's order score.

    3 stars: uses the budget to within 2%. 2 stars: within 10%. 1 star: fits.
    0 stars: no plan fits. Integer maths only (centavos), so no rounding surprises.
    """
    if not plan or not plan["fits"]:
        return 0
    left = plan["remaining"]
    if left * 50 <= budget_centavos:          # left <= 2% of the budget
        return 3
    if left * 10 <= budget_centavos:          # left <= 10%
        return 2
    return 1


def chef_mood_for_plan(stars, plan):
    """Which face the chef makes next to a budget plan."""
    if not plan:
        return "happy"
    if not plan["fits"]:
        return "worried"
    return "proud" if stars == 3 else "happy"


def _category_arg(value, default="Breakfast"):
    return value if value in CATEGORIES else default


def _describe_undo(entry):
    action, category, name, price = entry
    if action == "delete":
        return f"Undid adding {name} to {category}."
    if action == "add":
        return f"Undid deleting {name}; it is back in {category} at {format_pesos(price)}."
    return f"Undid the price change; {name} is back to {format_pesos(price)}."


def register_food_routes(app, service, login_required):

    def uid():
        return g.user["id"]

    def back_to_menu(category=None):
        return redirect(url_for("menu", category=_category_arg(category or
                                                               request.form.get("category"))))

    # ---------- menu + changes ----------

    @app.route("/menu")
    @login_required
    def menu():
        category = _category_arg(request.args.get("category"))
        # Shown once: the row that was just added or re-priced gets a highlight
        # and a "+P80.50" popup (static/style.css), then the session forgets it.
        just_added = session.pop("just_added", None)
        just_updated = session.pop("just_updated", None)
        return render_template(
            "menu.html",
            category=category,
            just_added=just_added if just_added and just_added[0] == category else None,
            just_updated=just_updated if just_updated and just_updated[0] == category else None,
            foods=service.menu(uid(), category),
            counts=service.counts(uid()),
            undo_count=service.undo_count(uid()),
        )

    @app.route("/foods/add", methods=["POST"])
    @login_required
    def add_food():
        category = request.form.get("category")
        try:
            price = parse_pesos(request.form.get("price"))
            cat, name, price = service.add_food(uid(), category, request.form.get("name"), price)
            flash(f"Added {name} to {cat} at {format_pesos(price)}.")
            session["just_added"] = [cat, name, price]       # highlighted once on the menu
        except InputError as err:
            flash(str(err), "error")
        return back_to_menu(category)

    @app.route("/foods/delete", methods=["POST"])
    @login_required
    def delete_food():
        try:
            cat, name, price = service.delete_food(uid(), request.form.get("category"),
                                                   request.form.get("name"))
            flash(f"Deleted {name} ({format_pesos(price)}) from {cat}. You can undo this.")
            return back_to_menu(cat)
        except InputError as err:
            flash(str(err), "error")
            return back_to_menu()

    @app.route("/foods/update", methods=["POST"])
    @login_required
    def update_price():
        try:
            new_price = parse_pesos(request.form.get("price"), "New price")
            cat, name, old, new = service.update_price(uid(), request.form.get("category"),
                                                       request.form.get("name"), new_price)
            flash(f"{name}: {format_pesos(old)} → {format_pesos(new)}.")
            session["just_updated"] = [cat, name, old, new]
            return back_to_menu(cat)
        except InputError as err:
            flash(str(err), "error")
            return back_to_menu()

    @app.route("/undo", methods=["POST"])
    @login_required
    def undo():
        entry = service.undo(uid())
        if entry is None:
            flash("Nothing to undo.", "error")
            return back_to_menu()
        flash(_describe_undo(entry))
        action, category, name, price = entry
        if action == "add":                                   # a deleted food came back
            session["just_added"] = [category, name, price]
        return back_to_menu(entry[1])

    # ---------- reads ----------

    @app.route("/search")
    @login_required
    def search():
        query = request.args.get("q", "")
        results, error = [], None
        if "q" in request.args:
            try:
                results = service.find(uid(), query)
                if not results:
                    error = f'"{query.strip()}" was not found.'
            except InputError as err:
                error = str(err)
        return render_template("search.html", query=query, results=results, error=error)

    @app.route("/total")
    @login_required
    def meal_total():
        # Each ticked box sends "Category|Name", so a food in two categories
        # (Adobo in Lunch and Dinner) is still one exact choice.
        selected = request.args.getlist("food")
        picks = [tuple(value.split("|", 1)) for value in selected if "|" in value]
        typed = request.args.get("typed", "")
        result, error = None, None
        if "go" in request.args:
            try:
                result = service.meal_total(uid(), picks, typed.split(","))
            except InputError as err:
                error = str(err)
        menus = {c: service.menu(uid(), c) for c in CATEGORIES}
        return render_template("total.html", menus=menus, selected=set(selected),
                               typed=typed, result=result, error=error)

    @app.route("/sort")
    @login_required
    def sort_price():
        chosen = [c for c in request.args.getlist("category") if c in CATEGORIES]
        rows, error = None, None
        if "go" in request.args:
            try:
                rows = service.sort_by_price(uid(), chosen)
            except InputError as err:
                error = str(err)
        return render_template("sort.html", chosen=chosen or list(CATEGORIES),
                               rows=rows, error=error)

    @app.route("/budget")
    @login_required
    def budget():
        chosen = [c for c in request.args.getlist("category") if c in CATEGORIES]
        amount = request.args.get("amount", "")
        plan, error, budget_centavos = None, None, None
        if "go" in request.args:
            try:
                budget_centavos = parse_pesos(amount, "Budget")
                if not chosen:
                    raise InputError("Choose at least one category.")
                plan = service.budget(uid(), chosen, budget_centavos)
            except ValueError as err:                 # InputError or BudgetError
                error = str(err)
        stars = plan_stars(plan, budget_centavos)
        return render_template("budget.html", chosen=chosen or list(CATEGORIES),
                               amount=amount, plan=plan, error=error,
                               today=date.today().isoformat(), stars=stars,
                               mood=chef_mood_for_plan(stars, plan))

    @app.route("/tree")
    @login_required
    def tree_view():
        category = _category_arg(request.args.get("category"))
        order = request.args.get("order", "levelorder")
        if order not in TRAVERSALS:
            order = "levelorder"
        foods, height = service.traversal(uid(), category, order)
        drawing = service.tree_drawing(uid(), category, order)
        return render_template("tree.html", category=category, order=order, foods=foods,
                               height=height, order_labels=ORDER_LABELS, drawing=drawing)

    # ---------- meal calendar ----------

    def to_day(day):
        return redirect(url_for("calendar_day", date=day.isoformat()))

    def form_day():
        """The date posted by a calendar form, or None after flashing why it is invalid."""
        try:
            return parse_date(request.form.get("date"))
        except InputError as err:
            flash(str(err), "error")
            return None

    @app.route("/calendar")
    @login_required
    def calendar_month():
        year, month = parse_month(request.args.get("month"))
        view = service.month_view(uid(), year, month)
        first = view["first"]
        prev_month = (first.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
        next_month = (first.replace(day=28) + timedelta(days=4)).strftime("%Y-%m")
        earliest, latest = date_window()
        return render_template(
            "calendar.html", view=view, today=date.today(), weekdays=WEEKDAY_NAMES,
            prev_month=prev_month if prev_month >= earliest.strftime("%Y-%m") else None,
            next_month=next_month if next_month <= latest.strftime("%Y-%m") else None)

    @app.route("/calendar/day")
    @login_required
    def calendar_day():
        try:
            day = parse_date(request.args.get("date"))
        except InputError as err:
            flash(str(err), "error")
            return redirect(url_for("calendar_month"))
        return render_template("calendar_day.html", view=service.day_view(uid(), day),
                               categories=CATEGORIES)

    @app.route("/calendar/plan", methods=["POST"])
    @login_required
    def calendar_plan():
        day = form_day()
        if day is None:
            return redirect(url_for("calendar_month"))
        try:
            cat, name, price = service.plan_meal(uid(), day, request.form.get("category"),
                                                 request.form.get("name"))
            flash(f"Planned {name} ({format_pesos(price)}) for {cat} on {day:%a %d %b}.")
        except InputError as err:
            flash(str(err), "error")
        return to_day(day)

    @app.route("/calendar/unplan", methods=["POST"])
    @login_required
    def calendar_unplan():
        day = form_day()
        if day is None:
            return redirect(url_for("calendar_month"))
        try:
            category = request.form.get("category")
            name, _ = service.unplan_meal(uid(), day, category)
            flash(f"Removed {name} from {category} on {day:%a %d %b}.")
        except InputError as err:
            flash(str(err), "error")
        return to_day(day)

    @app.route("/calendar/autoplan", methods=["POST"])
    @login_required
    def calendar_autoplan():
        day = form_day()
        if day is None:
            return redirect(url_for("calendar_month"))
        try:
            amount = parse_pesos(request.form.get("amount"), "Budget")
            plan = service.autoplan_day(uid(), day, amount)
            if plan["fits"]:
                names = ", ".join(name for _, name, _ in plan["picks"])
                flash(f"Planned {names} for {format_pesos(plan['total'])} "
                      f"({format_pesos(plan['remaining'])} left of {format_pesos(amount)}).")
            else:
                flash(f"Nothing fits in {format_pesos(amount)}: the cheapest choice for the empty "
                      f"slots costs {format_pesos(plan['cheapest_total'])}.", "error")
        except InputError as err:
            flash(str(err), "error")
        return to_day(day)

    @app.route("/calendar/goals", methods=["POST"])
    @login_required
    def calendar_goals():
        month = request.form.get("month", "")
        try:
            daily = parse_optional_pesos(request.form.get("daily"), "Daily budget")
            weekly = parse_optional_pesos(request.form.get("weekly"), "Weekly budget")
            monthly = parse_optional_pesos(request.form.get("monthly"), "Monthly budget")
            service.set_goals(uid(), daily, weekly, monthly)
            flash("Saved your calendar budgets.")
        except InputError as err:
            flash(str(err), "error")
        year, mon = parse_month(month)
        return redirect(url_for("calendar_month", month=f"{year:04d}-{mon:02d}"))

    @app.route("/budget/save", methods=["POST"])
    @login_required
    def budget_save():
        """Save the plan shown on the budget page. Only "Category|Name" is posted:
        prices are looked up in the trees again, so a changed form cannot alter them."""
        day = form_day()
        if day is None:
            return redirect(url_for("budget"))
        picks = [tuple(v.split("|", 1)) for v in request.form.getlist("pick") if "|" in v]
        try:
            meals = service.save_budget_plan(uid(), day, picks)
            total = sum(price for _, _, price in meals)
            flash(f"Saved the plan ({format_pesos(total)}) to {day:%a %d %b %Y}.")
        except InputError as err:
            flash(str(err), "error")
            return redirect(url_for("budget"))
        return to_day(day)
