"""Food pages (Milestone 7). Every route needs login and calls FoodService only.

Changes (add, delete, update, undo) are POST forms that redirect back to the
menu (post/redirect/get), so a browser refresh never repeats a change.
Reads (search, total, sort, budget, tree view) are GET forms.
"""

from flask import flash, g, redirect, render_template, request, url_for

from mealplano.dsa import CATEGORIES
from mealplano.food_service import TRAVERSALS
from mealplano.validation import InputError, format_pesos, parse_pesos

ORDER_LABELS = {
    "inorder": "In-order (left, node, right): cheapest first",
    "preorder": "Pre-order (node, left, right)",
    "postorder": "Post-order (left, right, node)",
    "levelorder": "Level-order (top level first, using the linked queue)",
}


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
        return render_template(
            "menu.html",
            category=category,
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
        plan, error = None, None
        if "go" in request.args:
            try:
                budget_centavos = parse_pesos(amount, "Budget")
                if not chosen:
                    raise InputError("Choose at least one category.")
                plan = service.budget(uid(), chosen, budget_centavos)
            except ValueError as err:                 # InputError or BudgetError
                error = str(err)
        return render_template("budget.html", chosen=chosen or list(CATEGORIES),
                               amount=amount, plan=plan, error=error)

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
