"""Thin repository wrappers around Django ORM for injectable data access."""

from __future__ import annotations

from decimal import Decimal

from .models import Address, Cart, CartItem, Order, OrderItem, Product, StoreConfig, TelegramUser


class DjangoCartRepo:
    """Wraps Cart and CartItem ORM queries."""

    def get_by_user(self, user: TelegramUser) -> Cart:
        return Cart.objects.get(user=user)

    def get_or_create(self, user: TelegramUser) -> Cart:
        cart, _ = Cart.objects.get_or_create(user=user)
        return cart

    def get_items(self, cart: Cart) -> list[CartItem]:
        return list(cart.items.select_related("product").all())

    def delete_items(self, cart: Cart) -> None:
        cart.items.all().delete()

    def find_item(self, cart: Cart, product_id: int) -> CartItem | None:
        return cart.items.filter(product_id=product_id).first()

    def get_item(self, item_id: int) -> CartItem:
        return CartItem.objects.get(id=item_id)

    def increment_item(self, item: CartItem) -> None:
        item.quantity += 1
        item.save(update_fields=["quantity"])

    def add_item(self, cart: Cart, product: Product, quantity: int = 1) -> CartItem:
        return CartItem.objects.create(cart=cart, product=product, quantity=quantity)

    def update_item_quantity(self, item: CartItem, quantity: int) -> None:
        item.quantity = quantity
        item.save(update_fields=["quantity"])

    def delete_item(self, item: CartItem) -> None:
        item.delete()


class DjangoProductRepo:
    """Wraps Product ORM queries."""

    def get_by_id(self, product_id: int) -> Product:
        return Product.objects.get(id=product_id)

    def get_for_update(self, product_id: int) -> Product:
        return Product.objects.select_for_update().get(id=product_id)

    def decrement_stock(self, product: Product, quantity: int) -> None:
        product.stock -= quantity
        product.save(update_fields=["stock"])


class DjangoAddressRepo:
    """Wraps Address ORM queries."""

    def get_by_user(self, user: TelegramUser) -> list[Address]:
        return list(Address.objects.filter(user=user))

    def get_by_id(self, address_id: int) -> Address:
        return Address.objects.get(id=address_id)

    def create(self, user: TelegramUser, label: str, full_address: str) -> Address:
        return Address.objects.create(user=user, label=label, full_address=full_address)

    def delete(self, address: Address) -> None:
        address.delete()


class DjangoUserRepo:
    """Wraps TelegramUser ORM queries."""

    def get_by_telegram(self, telegram_id: int) -> TelegramUser:
        return TelegramUser.objects.get(telegram_id=telegram_id)


class DjangoConfigRepo:
    """Wraps StoreConfig ORM queries for runtime configuration."""

    def get_all(self) -> dict[str, str]:
        return {config.key: config.value for config in StoreConfig.objects.all()}


class DjangoOrderRepo:
    """Wraps Order and OrderItem ORM creation."""

    def create(
        self,
        user: TelegramUser,
        total_amount: Decimal,
        shipping_address: str,
    ) -> Order:
        return Order.objects.create(
            user=user,
            total_amount=total_amount,
            shipping_address={"raw_address": shipping_address},
        )

    def create_item(
        self,
        order: Order,
        product: Product,
        quantity: int,
        price_at_purchase: Decimal,
    ) -> OrderItem:
        return OrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            price_at_purchase=price_at_purchase,
        )
