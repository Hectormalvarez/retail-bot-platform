from django.db import models


class TelegramUser(models.Model):
    """
    Caches Telegram account profiles. Tracks identity across private messages,
    group spaces, and administrative interactions.
    """

    telegram_id = models.BigIntegerField(unique=True, primary_key=True, db_index=True)
    username = models.CharField(max_length=32, blank=True, null=True)
    first_name = models.CharField(max_length=64)
    last_name = models.CharField(max_length=64, blank=True, null=True)
    is_active = models.BooleanField(
        default=True, help_text="False if the user stopped/blocked the bot"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.username or self.telegram_id}"


class Category(models.Model):
    """
    Manages catalog layers to cleanly map out inline keyboard button trees
    (CallbackQueryHandler) without overwhelming the chat screen.
    """

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, unique=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        blank=True,
        null=True,
        related_name="subcategories",
    )

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name


class Product(models.Model):
    """
    Stores individual stock items. Utilizes Telegram CDN caching to render
    product assets instantly across chat windows.
    """

    category = models.ForeignKey(
        Category, on_delete=models.PROTECT, related_name="products"
    )
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    stock = models.PositiveIntegerField(default=0)
    telegram_file_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,
        help_text="The internal Telegram file_id. Reuse this to bypass re-uploading assets to Telegram's CDN.",
    )
    is_visible = models.BooleanField(default=True)

    def __str__(self):
        return self.name


class Cart(models.Model):
    """
    A database-backed shopping cart. Keeps items safe if a user exits the chat,
    loses signal, or takes a day to complete checkout.
    """

    user = models.OneToOneField(
        TelegramUser, on_delete=models.CASCADE, related_name="cart"
    )
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Cart: {self.user}"


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ("cart", "product")


class Order(models.Model):
    """
    Tracks customer purchases and stores Telegram financial metadata to match
    webhooks against native invoice payloads.
    """

    STATUS_CHOICES = [
        ("PENDING", "Pending Payment"),
        ("COMPLETED", "Completed/Paid"),
        ("SHIPPED", "Shipped"),
        ("CANCELLED", "Cancelled"),
    ]

    user = models.ForeignKey(
        TelegramUser, on_delete=models.PROTECT, related_name="orders"
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="PENDING")
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)

    shipping_address = models.JSONField(
        blank=True,
        null=True,
        help_text="Raw shipping data returned from successful_payment",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Order #{self.id} - {self.user} ({self.status})"


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.RESTRICT)
    quantity = models.PositiveIntegerField()
    price_at_purchase = models.DecimalField(max_digits=10, decimal_places=2)
