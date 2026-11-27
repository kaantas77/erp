from django.urls import path

from . import views

app_name = "inventory"

urlpatterns = [
    path("urunler/", views.ProductListView.as_view(), name="product-list"),
    path("urunler/yeni/", views.ProductCreateView.as_view(), name="product-create"),
    path("urunler/<int:pk>/duzenle/", views.ProductUpdateView.as_view(), name="product-update"),
    path("kategoriler/yeni/", views.CategoryCreateView.as_view(), name="category-create"),
    path("depolar/", views.WarehouseListView.as_view(), name="warehouse-list"),
    path("depolar/yeni/", views.WarehouseCreateView.as_view(), name="warehouse-create"),
    path("mevcut/", views.StockOverviewView.as_view(), name="stock-overview"),
    path("hareketler/", views.StockMoveListView.as_view(), name="move-list"),
    path("hareketler/yeni/", views.StockMoveCreateView.as_view(), name="move-create"),
    path("sayimlar/", views.CountListView.as_view(), name="count-list"),
    path("sayimlar/yeni/", views.CountStartView.as_view(), name="count-start"),
    path("sayimlar/<int:pk>/", views.CountDetailView.as_view(), name="count-detail"),
    path("sayimlar/<int:pk>/kapat/", views.CountCloseView.as_view(), name="count-close"),
]
