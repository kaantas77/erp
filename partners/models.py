from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.urls import reverse

from core.models import TimeStampedModel
from core.utils import money


class Partner(TimeStampedModel):
    class Kind(models.TextChoices):
        CUSTOMER = "customer", "Musteri"
        SUPPLIER = "supplier", "Tedarikci"
        BOTH = "both", "Musteri + Tedarikci"

    code = models.CharField("Cari kodu", max_length=20, unique=True)
    name = models.CharField("Unvan", max_length=200)
    kind = models.CharField("Tur", max_length=10, choices=Kind.choices, default=Kind.CUSTOMER)
    tax_no = models.CharField("Vergi no", max_length=20, blank=True)
    tax_office = models.CharField("Vergi dairesi", max_length=80, blank=True)
    phone = models.CharField("Telefon", max_length=30, blank=True)
    email = models.EmailField("E-posta", blank=True)
    address = models.TextField("Adres", blank=True)
    is_active = models.BooleanField("Aktif", default=True)

    class Meta:
        verbose_name = "Cari"
        verbose_name_plural = "Cariler"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"

    @property
    def is_customer(self) -> bool:
        return self.kind in {self.Kind.CUSTOMER, self.Kind.BOTH}

    @property
    def is_supplier(self) -> bool:
        return self.kind in {self.Kind.SUPPLIER, self.Kind.BOTH}

    def balance(self) -> Decimal:
        total = self.entries.aggregate(total=Sum(models.F("debit") - models.F("credit")))["total"]
        return money(total or Decimal("0"))

    def get_absolute_url(self) -> str:
        return reverse("partners:partner-detail", args=[self.pk])


class LedgerEntry(TimeStampedModel):
    """Cari hareket defteri. Bakiye = borc - alacak (pozitif: bize borclu)."""

    class Source(models.TextChoices):
        INVOICE = "invoice", "Fatura"
        PAYMENT = "payment", "Tahsilat/Odeme"
        MANUAL = "manual", "Manuel"
        OPENING = "opening", "Acılıs bakiyesi"

    partner = models.ForeignKey(
        Partner, verbose_name="Cari", on_delete=models.PROTECT, related_name="entries"
    )
    date = models.DateField("Tarih")
    description = models.CharField("Aciklama", max_length=200)
    debit = models.DecimalField("Borc", max_digits=12, decimal_places=2, default=0)
    credit = models.DecimalField("Alacak", max_digits=12, decimal_places=2, default=0)
    source = models.CharField(
        "Kaynak", max_length=10, choices=Source.choices, default=Source.MANUAL
    )
    source_ref = models.CharField("Kaynak belge", max_length=40, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Islem yapan",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="ledger_entries",
    )

    class Meta:
        verbose_name = "Cari hareket"
        verbose_name_plural = "Cari hareketler"
        ordering = ["date", "id"]
        indexes = [models.Index(fields=["partner", "date"])]

    def __str__(self) -> str:
        return f"{self.partner.code} {self.date} {self.debit}/{self.credit}"

    @property
    def signed_amount(self) -> Decimal:
        return money(self.debit - self.credit)
