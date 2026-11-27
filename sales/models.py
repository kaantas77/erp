from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone

from core.models import TimeStampedModel
from core.utils import money, next_number, vat_split
from inventory.models import Product, Warehouse
from partners.models import Partner


class Order(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Taslak"
        CONFIRMED = "confirmed", "Onaylandi (rezerve)"
        SHIPPED = "shipped", "Sevk edildi"
        CANCELLED = "cancelled", "Iptal"

    number = models.CharField("Siparis no", max_length=32, unique=True, blank=True)
    partner = models.ForeignKey(
        Partner, verbose_name="Musteri", on_delete=models.PROTECT, related_name="orders"
    )
    warehouse = models.ForeignKey(
        Warehouse, verbose_name="Sevk deposu", on_delete=models.PROTECT, related_name="orders"
    )
    status = models.CharField("Durum", max_length=10, choices=Status.choices, default=Status.DRAFT)
    order_date = models.DateField("Siparis tarihi", default=timezone.localdate)
    note = models.CharField("Not", max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Olusturan",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="orders",
    )

    class Meta:
        verbose_name = "Siparis"
        verbose_name_plural = "Siparisler"
        ordering = ["-order_date", "-id"]

    def __str__(self) -> str:
        return self.number or f"Siparis #{self.pk}"

    def save(self, *args, **kwargs):
        if not self.number:
            self.number = next_number(Order, "SIP")
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
        return reverse("sales:order-detail", args=[self.pk])


class OrderReservation(TimeStampedModel):
    """Siparis onayinda ayrilan miktar.

    Rezervasyon fiziksel stok hareketi degildir; sadece "bu mal baskasina
    satilmasin" demektir. Fiziksel cikis sevk adiminda StockMove ile yazilir.
    """

    order_line = models.ForeignKey(
        "sales.OrderLine",
        verbose_name="Siparis satiri",
        on_delete=models.CASCADE,
        related_name="reservations",
    )
    warehouse = models.ForeignKey(
        Warehouse, verbose_name="Depo", on_delete=models.PROTECT, related_name="order_reservations"
    )
    quantity = models.DecimalField("Rezerve miktar", max_digits=14, decimal_places=3)

    class Meta:
        verbose_name = "Rezervasyon"
        verbose_name_plural = "Rezervasyonlar"

    def __str__(self) -> str:
        return f"{self.order_line_id}: {self.quantity}"


class OrderLine(TimeStampedModel):
    order = models.ForeignKey(
        Order, verbose_name="Siparis", on_delete=models.CASCADE, related_name="lines"
    )
    product = models.ForeignKey(
        Product, verbose_name="Urun", on_delete=models.PROTECT, related_name="order_lines"
    )
    quantity = models.DecimalField("Miktar", max_digits=14, decimal_places=3, default=1)
    unit_price = models.DecimalField("Birim fiyat", max_digits=12, decimal_places=2, default=0)
    discount_pct = models.DecimalField("Iskonto %", max_digits=5, decimal_places=2, default=0)
    vat_rate = models.DecimalField("KDV %", max_digits=5, decimal_places=2, default=Decimal("20"))

    class Meta:
        verbose_name = "Siparis satiri"
        verbose_name_plural = "Siparis satirlari"
        ordering = ["id"]

    def __str__(self) -> str:
        return f"{self.product.sku} x {self.quantity}"

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
