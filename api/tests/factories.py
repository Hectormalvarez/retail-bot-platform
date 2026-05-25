import factory
from store.models import Cart, Category, Product, TelegramUser

class TelegramUserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = TelegramUser

    # Sequence ensures every mock user gets a unique ID to prevent database collisions
    telegram_id = factory.Sequence(lambda n: 1000 + n)
    username = factory.Sequence(lambda n: f"user_{n}")
    first_name = factory.Faker("first_name")


class CategoryFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Category

    name = factory.Sequence(lambda n: f"Category {n}")
    slug = factory.Sequence(lambda n: f"category-{n}")


class ProductFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Product

    # SubFactory automatically builds and attaches a Category if we don't explicitly provide one
    category = factory.SubFactory(CategoryFactory)
    name = factory.Faker("word")
    description = factory.Faker("sentence")
    price = "15.00"
    stock = 100


class CartFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Cart

    user = factory.SubFactory(TelegramUserFactory)