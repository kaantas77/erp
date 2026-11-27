from django.urls import path

from . import views

app_name = "sales"

urlpatterns = [
    path("", views.OrderListView.as_view(), name="order-list"),
    path("yeni/", views.OrderCreateView.as_view(), name="order-create"),
    path("<int:pk>/", views.OrderDetailView.as_view(), name="order-detail"),
    path("<int:pk>/duzenle/", views.OrderUpdateView.as_view(), name="order-update"),
    path("<int:pk>/<str:action>/", views.OrderActionView.as_view(), name="order-action"),
]
