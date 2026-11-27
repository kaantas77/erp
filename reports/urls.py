from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("stok/", views.StockReportView.as_view(), name="stock"),
    path("stok/csv/", views.StockCsvExportView.as_view(), name="stock-csv"),
    path("cari/", views.PartnerBalanceReportView.as_view(), name="partner-balances"),
    path("cari/csv/", views.PartnerCsvExportView.as_view(), name="partner-csv"),
    path("satis/", views.SalesReportView.as_view(), name="sales"),
    path("sayim-fark/", views.CountVarianceReportView.as_view(), name="count-variance"),
    path("acik-siparis/", views.OpenOrdersReportView.as_view(), name="open-orders"),
]
