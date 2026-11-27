from __future__ import annotations

from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField("Olusturulma", auto_now_add=True)
    updated_at = models.DateTimeField("Guncellenme", auto_now=True)

    class Meta:
        abstract = True
