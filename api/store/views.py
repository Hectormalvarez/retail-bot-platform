from rest_framework import viewsets
from .models import Category, Product
from .serializers import CategorySerializer, ProductSerializer

class CategoryViewSet(viewsets.ModelViewSet):
    """
    Handles lifecycle operations for product categories.
    """
    queryset = Category.objects.all()
    serializer_class = CategorySerializer

class ProductViewSet(viewsets.ModelViewSet):
    """
    Handles lifecycle operations for products. Supports filtering by category.
    """
    queryset = Product.objects.all()
    serializer_class = ProductSerializer
    filterset_fields = ['category']