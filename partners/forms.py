from __future__ import annotations

from django import forms

from .models import LedgerEntry, Partner


class PartnerForm(forms.ModelForm):
    class Meta:
        model = Partner
        fields = [
            "code",
            "name",
            "kind",
            "tax_no",
            "tax_office",
            "phone",
            "email",
            "address",
            "is_active",
        ]
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}


class PaymentForm(forms.Form):
    date = forms.DateField(label="Tarih", widget=forms.DateInput(attrs={"type": "date"}))
    amount = forms.DecimalField(label="Tutar", max_digits=12, decimal_places=2, min_value=0.01)
    description = forms.CharField(label="Aciklama", required=False, max_length=200)


class LedgerEntryForm(forms.ModelForm):
    class Meta:
        model = LedgerEntry
        fields = ["date", "description", "debit", "credit", "source_ref"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}

    def clean(self):
        cleaned = super().clean()
        debit = cleaned.get("debit") or 0
        credit = cleaned.get("credit") or 0
        if debit and credit:
            raise forms.ValidationError("Hem borc hem alacak girilemez.")
        if not debit and not credit:
            raise forms.ValidationError("Borc veya alacak girilmeli.")
        return cleaned
