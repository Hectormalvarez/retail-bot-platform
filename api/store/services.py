"""Business logic extracted from views for reuse and testability."""

from __future__ import annotations

from decimal import Decimal

from .models import Order
from .repositories import (
    DjangoCartRepo,
    DjangoOrderRepo,
    DjangoProductRepo,
    DjangoUserRepo,
)


class OrderService:
    """Handles the checkout flow – stock validation, order creation, cart cleanup.

    Accepts injected repository instances so it can be unit-tested without a DB.
    Transaction management is the caller's responsibility (typically the view).
    """

    def __init__(
        self,
        user_repo: DjangoUserRepo | None = None,
        cart_repo: DjangoCartRepo | None = None,
        product_repo: DjangoProductRepo | None = None,
        order_repo: DjangoOrderRepo | None = None,
    ):
        self.users = user_repo or DjangoUserRepo()
        self.carts = cart_repo or DjangoCartRepo()
        self.products = product_repo or DjangoProductRepo()
        self.orders = order_repo or DjangoOrderRepo()

    def create_order(
        self, user_id: int, shipping_address: str
    ) -> tuple[Order | None, str | None]:
        """Create an order from the user's cart.

        Returns
        -------
        (order, None) on success, or (None, error_message) on failure.
        """
        try:
            user = self.users.get_by_telegram(user_id)
            cart = self.carts.get_by_user(user)
        except Exception:
            return None, "Invalid user context or missing cart"

        cart_items = self.carts.get_items(cart)
        if not cart_items:
            return None, "Shopping cart is empty"

        total_amount: Decimal = Decimal("0.00")
        for item in cart_items:
            product = self.products.get_for_update(item.product.id)
            if product.stock < item.quantity:
                return None, f"Insufficient stock available for {product.name}"
            total_amount += product.price * item.quantity

        order = self.orders.create(
            user=user,
            total_amount=total_amount,
            shipping_address=shipping_address,
        )

        for item in cart_items:
            product = self.products.get_by_id(item.product.id)
            self.products.decrement_stock(product, item.quantity)
            self.orders.create_item(
                order=order,
                product=item.product,
                quantity=item.quantity,
                price_at_purchase=item.product.price,
            )

        self.carts.delete_items(cart)

        return order, None
