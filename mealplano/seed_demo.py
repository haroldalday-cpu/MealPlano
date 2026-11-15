"""Create (or reset) a demo account with a realistic Filipino menu, for the defense demo.

Run from the project folder:
    python -m mealplano.seed_demo

The demo login is listed in README.md. Running this again resets the demo
account's foods to the list below, and plans its meal calendar for the next
10 days starting today (one day deliberately over budget); other accounts are not touched.
Stop the web server first, or log the demo account out and in again afterwards,
because a running server keeps each logged-in user's trees in memory.
"""

from datetime import date, timedelta
from pathlib import Path

from mealplano import auth, db
from mealplano.food_service import FoodService

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "mealplano-demo"      # local demo only; see README.md
DB_PATH = Path(__file__).resolve().parent.parent / "instance" / "mealplano.db"

# Deliberately NOT in alphabetical order, the way a person would type them.
MENU = [
    ("Breakfast", "Tapsilog", 9500), ("Breakfast", "Champorado", 4500),
    ("Breakfast", "Pandesal with Egg", 3500), ("Breakfast", "Arroz Caldo", 4000),
    ("Breakfast", "Longsilog", 9000), ("Breakfast", "Taho", 2500),
    ("Lunch", "Sinigang na Baboy", 12000), ("Lunch", "Adobo", 8050),
    ("Lunch", "Tinola", 7500), ("Lunch", "Kare-Kare", 15000),
    ("Lunch", "Pancit Canton", 6500), ("Lunch", "Bicol Express", 7500),
    ("Dinner", "Bistek Tagalog", 9000), ("Dinner", "Menudo", 8500),
    ("Dinner", "Sisig", 11000), ("Dinner", "Laing", 6000),
    ("Dinner", "Lechon Kawali", 13000), ("Dinner", "Pinakbet", 6000),
    ("Snacks", "Turon", 2000), ("Snacks", "Banana Cue", 2000),
    ("Snacks", "Puto", 1500), ("Snacks", "Halo-Halo", 6500),
    ("Snacks", "Kwek-Kwek", 2500), ("Snacks", "Bibingka", 3525),
]

# Calendar budgets in centavos: P200 a day, P1,300 a week, P5,000 a month.
GOALS = (20000, 130000, 500000)

# One day per row, starting today: (Breakfast, Lunch, Dinner, Snacks); None = not planned.
CALENDAR = [
    ("Taho", "Pancit Canton", "Menudo", "Kwek-Kwek"),               # P200.00, exactly the budget
    ("Pandesal with Egg", "Tinola", "Pinakbet", "Puto"),             # P185.00
    ("Champorado", "Adobo", "Laing", None),                          # P185.50
    ("Arroz Caldo", "Bicol Express", "Pinakbet", "Turon"),           # P195.00
    ("Tapsilog", "Kare-Kare", "Lechon Kawali", "Halo-Halo"),         # P440.00, fiesta: over budget
    ("Taho", "Pancit Canton", "Laing", "Banana Cue"),                # P170.00
    (None, "Sinigang na Baboy", None, None),                         # P120.00, only lunch so far
    ("Pandesal with Egg", "Adobo", "Menudo", None),                  # P200.50, just over
    ("Arroz Caldo", "Tinola", "Laing", "Puto"),                      # P190.00
    ("Champorado", "Bicol Express", "Pinakbet", "Kwek-Kwek"),        # P205.00, just over
]


def main():
    DB_PATH.parent.mkdir(exist_ok=True)
    db_path = str(DB_PATH)
    db.init_db(db_path)

    row = db.get_user_by_username(db_path, DEMO_USERNAME)
    if row is None:
        user_id = auth.register(db_path, DEMO_USERNAME, DEMO_PASSWORD)
        print(f"Created demo account '{DEMO_USERNAME}'.")
    else:
        user_id = row["id"]
        with db.connect(db_path) as conn:
            conn.execute("DELETE FROM foods WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM meal_plans WHERE user_id = ?", (user_id,))
        print(f"Reset foods and calendar for existing demo account '{DEMO_USERNAME}'.")

    service = FoodService(db_path)
    for category, name, price in MENU:
        service.add_food(user_id, category, name, price)
    print(f"Added {len(MENU)} foods. Database: {db_path}")

    service.set_goals(user_id, *GOALS)
    today = date.today()
    categories = ("Breakfast", "Lunch", "Dinner", "Snacks")
    for offset, names in enumerate(CALENDAR):
        picks = [(c, n) for c, n in zip(categories, names) if n is not None]
        service.save_budget_plan(user_id, today + timedelta(days=offset), picks)
    print(f"Planned {len(CALENDAR)} days from {today:%d %b %Y} and set the calendar budgets.")
    print("Log in with the demo account listed in README.md.")


if __name__ == "__main__":
    main()
