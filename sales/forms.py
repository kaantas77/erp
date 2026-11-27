from __future__ import annotations

from django import forms
from django.forms import inlineformset_factory

from inventory.models import Warehouse
from partners.models import Partner

from .models import Order, OrderLine


class OrderForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["partner", "warehouse", "order_date", "note"]
        widgets = {"order_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["partner"].queryset = Partner.objects.filter(
            is_active=True, kind__in=[Partner.Kind.CUSTOMER, Partner.Kind.BOTH]
        )
        self.fields["warehouse"].queryset = Warehouse.objects.filter(is_active=True)


OrderLineFormSet = inlineformset_factory(
    Order,
    OrderLine,
    fields=["product", "quantity", "unit_price", "discount_pct", "vat_rate"],
    extra=3,
    can_delete=True,
)
