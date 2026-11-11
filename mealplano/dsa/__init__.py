"""MealPLANO data structures and algorithms. No Flask or SQL imports here."""

from .node import FoodNode, make_key, validate_price
from .bst import BST
from .avl import AVLTree
from .price_tree import PriceAVLTree
from .linked_queue import LinkedQueue
from .stack import LinkedStack, UndoHistory
from .sorting import merge_sort, quick_sort, sort_by_price
from .budget import BudgetError, cheapest_food, exhaustive_best, plan_within_budget

CATEGORIES = ("Breakfast", "Lunch", "Dinner", "Snacks")
