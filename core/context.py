from __future__ import annotations

from django.utils import timezone


def navigation(request):
    """Tum sablonlarda kullanilan temel baglam."""
    return {
        "brand": "Depo ERP",
        "today": timezone.localdate(),
    }
