from django.contrib import admin
from .models import Address, TelegramUser, Category, Product, Cart, CartItem, Order, OrderItem


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = ("telegram_id", "username", "first_name", "is_active", "created_at")
    search_fields = ("telegram_id", "username", "first_name")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "category", "price", "stock", "is_visible")
    list_filter = ("category", "is_visible")
    search_fields = ("name", "description")


admin.site.register(Category)
admin.site.register(Cart)
admin.site.register(CartItem)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(Address)
