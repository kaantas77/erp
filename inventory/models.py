from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.urls import reverse

from core.models import TimeStampedModel


class Category(TimeStampedModel):
    name = models.CharField("Ad", max_length=120, unique=True)

    class Meta:
        verbose_name = "Kategori"
        verbose_name_plural = "Kategoriler"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class Product(TimeStampedModel):
    class Unit(models.TextChoices):
        PIECE = "adet", "Adet"
        KG = "kg", "Kg"
        LITER = "lt", "Lt"
        PACK = "paket", "Paket"
        BOX = "kutu", "Kutu"

    sku = models.CharField("Stok kodu", max_length=40, unique=True)
    name = models.CharField("Urun adi", max_length=200)
    category = models.ForeignKey(
        Category,
        verbose_name="Kategori",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="products",
    )
    unit = models.CharField("Birim", max_length=10, choices=Unit.choices, default=Unit.PIECE)
    purchase_price = models.DecimalField("Alis fiyati", max_digits=12, decimal_places=2, default=0)
    sale_price = models.DecimalField("Satis fiyati", max_digits=12, decimal_places=2, default=0)
    vat_rate = models.DecimalField("KDV %", max_digits=5, decimal_places=2, default=Decimal("20"))
    reorder_level = models.DecimalField("Kritik stok", max_digits=12, decimal_places=3, default=0)
    is_active = models.BooleanField("Aktif", default=True)

    class Meta:
        verbose_name = "Urun"
        verbose_name_plural = "Urunler"
        ordering = ["sku"]

    def __str__(self) -> str:
        return f"{self.sku} - {self.name}"

    def on_hand(self, warehouse: Warehouse | None = None) -> Decimal:
        return on_hand(self, warehouse)

    def get_absolute_url(self) -> str:
        return reverse("inventory:product-list")


class Warehouse(TimeStampedModel):
    code = models.CharField("Depo kodu", max_length=20, unique=True)
    name = models.CharField("Depo adi", max_length=120)
    is_active = models.BooleanField("Aktif", default=True)

    class Meta:
        verbose_name = "Depo"
        verbose_name_plural = "Depolar"
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class StockMoveQuerySet(models.QuerySet):
    def for_product(self, product: Product):
        return self.filter(product=product)

    def quantity_total(self) -> Decimal:
        return self.aggregate(total=Sum("quantity"))["total"] or Decimal("0")


class StockMove(TimeStampedModel):
    class Kind(models.TextChoices):
        IN = "in", "Giris"
        OUT = "out", "Cikis"
        TRANSFER = "transfer", "Transfer"
        COUNT = "count", "Sayim duzeltmesi"

    product = models.ForeignKey(
        Product, verbose_name="Urun", on_delete=models.PROTECT, related_name="moves"
    )
    warehouse = models.ForeignKey(
        Warehouse, verbose_name="Depo", on_delete=models.PROTECT, related_name="moves"
    )
    quantity = models.DecimalField("Miktar", max_digits=14, decimal_places=3)
    unit_cost = models.DecimalField("Birim maliyet", max_digits=12, decimal_places=2, default=0)
    kind = models.CharField("Tur", max_length=12, choices=Kind.choices, default=Kind.IN)
    reference = models.CharField("Referans", max_length=40, blank=True)
    note = models.CharField("Not", max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Islem yapan",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="stock_moves",
    )

    objects = StockMoveQuerySet.as_manager()

    class Meta:
        verbose_name = "Stok hareketi"
        verbose_name_plural = "Stok hareketleri"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["product", "warehouse"]),
            models.Index(fields=["kind", "created_at"]),
        ]

    def __str__(self) -> str:
        sign = "+" if self.quantity >= 0 else ""
        return f"{self.product.sku} {sign}{self.quantity} ({self.get_kind_display()})"

    def clean(self) -> None:
        super().clean()
        if not self.quantity:
            raise ValidationError({"quantity": "Miktar sifir olamaz."})

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)


def on_hand(product: Product, warehouse: Warehouse | None = None) -> Decimal:
    """Urunun (opsiyonel olarak depo bazinda) mevcut stogu."""
    moves = StockMove.objects.filter(product=product)
    if warehouse is not None:
        moves = moves.filter(warehouse=warehouse)
    return moves.quantity_total()


class CountSession(TimeStampedModel):
    class Status(models.TextChoices):
        DRAFT = "draft", "Taslak"
        OPEN = "open", "Sayim acik"
        CLOSED = "closed", "Kapatildi"
        CANCELLED = "cancelled", "Iptal"

    number = models.CharField("Sayim no", max_length=32, unique=True, blank=True)
    warehouse = models.ForeignKey(
        Warehouse, verbose_name="Depo", on_delete=models.PROTECT, related_name="count_sessions"
    )
    status = models.CharField("Durum", max_length=10, choices=Status.choices, default=Status.OPEN)
    note = models.CharField("Not", max_length=200, blank=True)
    closed_at = models.DateTimeField("Kapanis", null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Baslatan",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="count_sessions",
    )

    class Meta:
        verbose_name = "Sayim"
        verbose_name_plural = "Sayimlar"
        ordering = ["-created_at", "-id"]

    def __str__(self) -> str:
        return self.number or f"Sayim #{self.pk}"

    def save(self, *args, **kwargs):
        if not self.number:
            from core.utils import next_number

            self.number = next_number(CountSession, "SAY", width=3)
        return super().save(*args, **kwargs)

    @property
    def is_open(self) -> bool:
        return self.status == self.Status.OPEN

    @property
    def total_variance(self) -> Decimal:
        return sum((line.variance or Decimal("0") for line in self.lines.all()), Decimal("0"))

    @property
    def variance_count(self) -> int:
        return sum(1 for line in self.lines.all() if line.variance)

    @property
    def uncounted_count(self) -> int:
        return sum(1 for line in self.lines.all() if line.counted_qty is None)

    def get_absolute_url(self) -> str:
        return reverse("inventory:count-detail", args=[self.pk])


class CountLine(TimeStampedModel):
    session = models.ForeignKey(
        CountSession, verbose_name="Sayim", on_delete=models.CASCADE, related_name="lines"
    )
    product = models.ForeignKey(
        Product, verbose_name="Urun", on_delete=models.PROTECT, related_name="count_lines"
    )
    system_qty = models.DecimalField("Sistem miktari", max_digits=14, decimal_places=3, default=0)
    counted_qty = models.DecimalField(
        "Sayilan", max_digits=14, decimal_places=3, null=True, blank=True
    )

    class Meta:
        verbose_name = "Sayim satiri"
        verbose_name_plural = "Sayim satirlari"
        ordering = ["product__sku"]
        constraints = [
            models.UniqueConstraint(fields=["session", "product"], name="unique_count_line")
        ]

    def __str__(self) -> str:
        return f"{self.product.sku}: {self.counted_qty}"

    @property
    def variance(self) -> Decimal | None:
        if self.counted_qty is None:
            return None
        return self.counted_qty - self.system_qty
