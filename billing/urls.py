from django.urls import path

from . import views

app_name = "billing"

urlpatterns = [
    path("", views.InvoiceListView.as_view(), name="invoice-list"),
    path("yeni/", views.InvoiceCreateView.as_view(), name="invoice-create"),
    path("<int:pk>/", views.InvoiceDetailView.as_view(), name="invoice-detail"),
    path("<int:pk>/duzenle/", views.InvoiceUpdateView.as_view(), name="invoice-update"),
    path("<int:pk>/<str:action>/", views.InvoiceActionView.as_view(), name="invoice-action"),
]
