from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.models import TimeStampedModel
from core.utils import money, next_number, vat_split
from inventory.models import Product
from partners.models import Partner


class Invoice(TimeStampedModel):
    class Kind(models.TextChoices):
        SALES = "sales", "Satis faturasi"
        PURCHASE = "purchase", "Alis faturasi"

    class Status(models.TextChoices):
        DRAFT = "draft", "Taslak"
        ISSUED = "issued", "Kesildi"
        PAID = "paid", "Odendi"
        CANCELLED = "cancelled", "Iptal"

    number = models.CharField("Fatura no", max_length=32, unique=True, blank=True)
    kind = models.CharField("Tur", max_length=10, choices=Kind.choices, default=Kind.SALES)
    partner = models.ForeignKey(
        Partner, verbose_name="Cari", on_delete=models.PROTECT, related_name="invoices"
    )
    status = models.CharField("Durum", max_length=10, choices=Status.choices, default=Status.DRAFT)
    date = models.DateField("Fatura tarihi", default=timezone.localdate)
    due_date = models.DateField("Vade", null=True, blank=True)
    order = models.ForeignKey(
        "sales.Order",
        verbose_name="Siparis",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invoices",
    )
    note = models.CharField("Not", max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Kesen",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invoices",
    )

    class Meta:
        verbose_name = "Fatura"
        verbose_name_plural = "Faturalar"
        ordering = ["-date", "-id"]

    def __str__(self) -> str:
        return self.number or f"Fatura #{self.pk}"

    def save(self, *args, **kwargs):
        if not self.number:
            prefix = "SF" if self.kind == self.Kind.SALES else "AF"
            self.number = next_number(Invoice, prefix)
        return super().save(*args, **kwargs)

    @property
    def is_editable(self) -> bool:
        return self.status == self.Status.DRAFT

    @property
    def net_total(self) -> Decimal:
        return money(sum((line.net_amount for line in self.lines.all()), Decimal("0")))

    @property
    def vat_total(self) -> Decimal:
        return money(sum((line.vat_amount for line in self.lines.all()), Decimal("0")))

    @property
    def grand_total(self) -> Decimal:
        return money(self.net_total + self.vat_total)

    def get_absolute_url(self) -> str:
        return reverse("billing:invoice-detail", args=[self.pk])


class InvoiceLine(TimeStampedModel):
    invoice = models.ForeignKey(
        Invoice, verbose_name="Fatura", on_delete=models.CASCADE, related_name="lines"
    )
    product = models.ForeignKey(
        Product,
        verbose_name="Urun",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="invoice_lines",
    )
    description = models.CharField("Aciklama", max_length=200, blank=True)
    quantity = models.DecimalField("Miktar", max_digits=14, decimal_places=3, default=1)
    unit_price = models.DecimalField("Birim fiyat", max_digits=12, decimal_places=2, default=0)
    discount_pct = models.DecimalField("Iskonto %", max_digits=5, decimal_places=2, default=0)
    vat_rate = models.DecimalField("KDV %", max_digits=5, decimal_places=2, default=Decimal("20"))

    class Meta:
        verbose_name = "Fatura satiri"
        verbose_name_plural = "Fatura satirlari"
        ordering = ["id"]

    def __str__(self) -> str:
        return self.display_name

    @property
    def display_name(self) -> str:
        if self.product:
            return f"{self.product.sku} - {self.product.name}"
        return self.description or "-"

    @property
    def net_amount(self) -> Decimal:
        gross = self.quantity * self.unit_price
        return money(gross * (Decimal("100") - self.discount_pct) / Decimal("100"))

    @property
    def vat_amount(self) -> Decimal:
        return vat_split(self.net_amount, self.vat_rate)[0]

    @property
    def gross_amount(self) -> Decimal:
        return money(self.net_amount + self.vat_amount)
