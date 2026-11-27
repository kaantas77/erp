from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("core.urls")),
    path("stok/", include("inventory.urls")),
    path("cari/", include("partners.urls")),
    path("siparis/", include("sales.urls")),
    path("fatura/", include("billing.urls")),
    path("rapor/", include("reports.urls")),
    path("hesap/", include("django.contrib.auth.urls")),
]
