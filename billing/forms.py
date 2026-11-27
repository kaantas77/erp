from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from partners.models import Partner

from .models import Invoice, InvoiceLine


class InvoiceForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ["kind", "partner", "date", "due_date", "order", "note"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date"}),
            "due_date": forms.DateInput(attrs={"type": "date"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["partner"].queryset = Partner.objects.filter(is_active=True)
        self.fields["order"].queryset = self.fields["order"].queryset.select_related("partner")


InvoiceLineFormSet = inlineformset_factory(
    Invoice,
    InvoiceLine,
    fields=["product", "description", "quantity", "unit_price", "discount_pct", "vat_rate"],
    extra=3,
    can_delete=True,
)
