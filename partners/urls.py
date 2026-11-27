from django.urls import path

from . import views

app_name = "partners"

urlpatterns = [
    path("", views.PartnerListView.as_view(), name="partner-list"),
    path("yeni/", views.PartnerCreateView.as_view(), name="partner-create"),
    path("<int:pk>/", views.PartnerDetailView.as_view(), name="partner-detail"),
    path("<int:pk>/duzenle/", views.PartnerUpdateView.as_view(), name="partner-update"),
]
