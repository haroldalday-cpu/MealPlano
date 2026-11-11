"""Create (or reset) a demo account with a realistic Filipino menu, for the defense demo.

Run from the project folder:
    python -m mealplano.seed_demo

The demo login is listed in README.md. Running this again resets the demo
account's foods to the list below; other accounts are not touched.
Stop the web server first, or log the demo account out and in again afterwards,
because a running server keeps each logged-in user's trees in memory.
"""

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
        print(f"Reset foods for existing demo account '{DEMO_USERNAME}'.")

    service = FoodService(db_path)
    for category, name, price in MENU:
        service.add_food(user_id, category, name, price)
    print(f"Added {len(MENU)} foods. Database: {db_path}")
    print("Log in with the demo account listed in README.md.")


if __name__ == "__main__":
    main()
