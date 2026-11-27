from __future__ import annotations

from django.db import transaction

from partners.models import LedgerEntry
from partners.services import add_entry

from .models import Invoice


class InvoiceError(Exception):
    """Fatura akisinda is kurali ihlali."""


@transaction.atomic
def issue_invoice(invoice: Invoice, user=None) -> None:
    """Faturayi keser ve cariye isler (satista borc, alista alacak)."""
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status != Invoice.Status.DRAFT:
        raise InvoiceError("Sadece taslak faturalar kesilebilir.")
    if not invoice.lines.exists():
        raise InvoiceError("Faturada satir yok.")

    add_entry(
        partner=invoice.partner,
        date=invoice.date,
        description=f"{invoice.number} nolu {invoice.get_kind_display()}",
        debit=invoice.grand_total if invoice.kind == Invoice.Kind.SALES else 0,
        credit=invoice.grand_total if invoice.kind == Invoice.Kind.PURCHASE else 0,
        source=LedgerEntry.Source.INVOICE,
        source_ref=invoice.number,
        user=user,
    )

    invoice.status = Invoice.Status.ISSUED
    invoice.save(update_fields=["status", "updated_at"])


@transaction.atomic
def cancel_invoice(invoice: Invoice, user=None) -> None:
    """Kesilmis faturanin cari kaydini ters kayitla kapatir."""
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status not in {Invoice.Status.ISSUED, Invoice.Status.PAID}:
        raise InvoiceError("Sadece kesilmis faturalar iptal edilebilir.")

    add_entry(
        partner=invoice.partner,
        date=invoice.date,
        description=f"{invoice.number} nolu fatura iptali",
        debit=invoice.grand_total if invoice.kind == Invoice.Kind.PURCHASE else 0,
        credit=invoice.grand_total if invoice.kind == Invoice.Kind.SALES else 0,
        source=LedgerEntry.Source.INVOICE,
        source_ref=invoice.number,
        user=user,
    )

    invoice.status = Invoice.Status.CANCELLED
    invoice.save(update_fields=["status", "updated_at"])


@transaction.atomic
def mark_paid(invoice: Invoice) -> None:
    invoice = Invoice.objects.select_for_update().get(pk=invoice.pk)
    if invoice.status != Invoice.Status.ISSUED:
        raise InvoiceError("Sadece kesilmis faturalar odendi olarak isaretlenebilir.")
    invoice.status = Invoice.Status.PAID
    invoice.save(update_fields=["status", "updated_at"])
