"""Tree node shared by the BST and the AVL tree (PRD Section 7)."""


def make_key(name):
    """Return the case-insensitive ordering key for a food name."""
    return name.strip().lower()


def validate_price(price_centavos):
    """Raise ValueError unless the price is a positive whole number of centavos."""
    # bool is a subclass of int, so reject it explicitly.
    if isinstance(price_centavos, bool) or not isinstance(price_centavos, int):
        raise ValueError("Price must be a whole number of centavos.")
    if price_centavos <= 0:
        raise ValueError("Price must be greater than zero.")


class FoodNode:
    def __init__(self, display_name, price_centavos):
        if not isinstance(display_name, str) or not display_name.strip():
            raise ValueError("Food name must not be empty.")
        validate_price(price_centavos)

        self.name_key = make_key(display_name)     # case-insensitive name, e.g. "adobo"
        self.key = self.name_key                   # ORDERING key: the name in BST/AVLTree;
                                                   # PriceAVLTree replaces it with (price, name_key)
        self.display_name = display_name.strip()   # shown to the user, e.g. "Adobo"
        self.price = price_centavos                # P80.50 is stored as 8050
        self.left = None
        self.right = None
        self.height = 1                            # used by the AVL tree only

    def __repr__(self):
        return f"FoodNode({self.display_name!r}, {self.price})"
