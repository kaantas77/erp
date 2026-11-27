from __future__ import annotations

from django.http import JsonResponse
from django.shortcuts import redirect
from django.views.decorators.http import require_GET


@require_GET
def home(request):
    if not request.user.is_authenticated:
        return redirect("login")
    return redirect("reports:dashboard")


@require_GET
def health(request):
    return JsonResponse({"status": "ok"})
