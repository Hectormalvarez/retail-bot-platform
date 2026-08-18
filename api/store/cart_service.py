"""Shopping cart business logic extracted for testability."""

from __future__ import annotations

from .models import CartItem
from .repositories import DjangoCartRepo, DjangoProductRepo, DjangoUserRepo


class CartService:
    """Handles cart operations – add/increment, update quantity, delete.

    Accepts injected repository instances so it can be unit-tested without a DB.
    """

    def __init__(
        self,
        user_repo: DjangoUserRepo | None = None,
        cart_repo: DjangoCartRepo | None = None,
        product_repo: DjangoProductRepo | None = None,
    ):
        self.users = user_repo or DjangoUserRepo()
        self.carts = cart_repo or DjangoCartRepo()
        self.products = product_repo or DjangoProductRepo()

    def add_or_increment(
        self, tg_id: int, product_id: int, quantity: int = 1
    ) -> CartItem | None:
        """Add a product to the user's cart, or increment if it already exists.

        Returns the CartItem, or None if the user/product does not exist.
        """
        if quantity <= 0:
            return None

        try:
            user = self.users.get_by_telegram(tg_id)
        except Exception:
            return None

        cart = self.carts.get_or_create(user)

        existing = self.carts.find_item(cart, product_id)
        if existing is not None:
            self.carts.increment_item_by(existing, quantity)
            return existing

        try:
            product = self.products.get_by_id(product_id)
        except Exception:
            return None

        return self.carts.add_item(cart, product, quantity=quantity)

    def update_quantity(self, item_id: int, new_qty: int) -> CartItem | None:
        """Update cart-item quantity.

        Returns None if the item was deleted (qty <= 0).
        """
        try:
            item = self.carts.get_item(item_id)
        except Exception:
            return None

        if new_qty <= 0:
            self.carts.delete_item(item)
            return None

        self.carts.update_item_quantity(item, new_qty)
        return item
