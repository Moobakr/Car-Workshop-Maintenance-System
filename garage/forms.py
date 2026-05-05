from django import forms
from .models import Client, Car, Visit, Worker, VisitPart, Expense, Payment
from django.forms import inlineformset_factory


class ClientForm(forms.ModelForm):
    class Meta:
        model = Client
        fields = ["name", "phone"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
        }


class CarForm(forms.ModelForm):
    class Meta:
        model = Car
        fields = ["client", "vin", "plate_number", "important_detail", "current_km"]
        widgets = {
            "client": forms.Select(attrs={"class": "form-control"}),
            "vin": forms.TextInput(attrs={"class": "form-control"}),
            "plate_number": forms.TextInput(attrs={"class": "form-control"}),
            "important_detail": forms.TextInput(attrs={"class": "form-control"}),
            "current_km": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
        }


class VisitForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["worker"].queryset = Worker.objects.order_by("name")

    class Meta:
        model = Visit
        fields = [
            "km_at_visit",
            "worker",
            "work_description",
            "notes",
        ]
        widgets = {
            "km_at_visit": forms.NumberInput(attrs={"class": "form-control", "min": 0}),
            "worker": forms.Select(attrs={"class": "form-control"}),
            "work_description": forms.Textarea(attrs={"class": "form-control", "rows": 5}),
            "notes": forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        }


class WorkerForm(forms.ModelForm):
    class Meta:
        model = Worker
        fields = ["name", "phone"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "form-control"}),
            "phone": forms.TextInput(attrs={"class": "form-control"}),
        }

class VisitPartForm(forms.ModelForm):
    class Meta:
        model = VisitPart
        fields = ["part_name", "client_cost", "workshop_cost"]
        widgets = {
            "part_name": forms.TextInput(attrs={"class": "form-control", "placeholder": "اسم القطعة"}),
            "client_cost": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "0.01", "placeholder": "على العميل"}),
            "workshop_cost": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "0.01", "placeholder": "على الورشة"}),
        }

class PaymentForm(forms.ModelForm):
    class Meta:
        model = Payment
        fields = ["cash_amount", "insta_amount"]
        widgets = {
            "cash_amount": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "0.01"}),
            "insta_amount": forms.NumberInput(attrs={"class": "form-control", "min": 0, "step": "0.01"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cash_amount"].required = False
        self.fields["insta_amount"].required = False

    def clean_cash_amount(self):
        return self.cleaned_data.get("cash_amount") or 0

    def clean_insta_amount(self):
        return self.cleaned_data.get("insta_amount") or 0

VisitPartFormSet = inlineformset_factory(
    Visit,
    VisitPart,
    form=VisitPartForm,
    extra=1,         # start with 1 empty row
    can_delete=True
)



class ExpenseForm(forms.ModelForm):
    class Meta:
        model = Expense
        fields = ["date", "category", "amount", "note"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"}),
            "category": forms.TextInput(attrs={"class": "form-control"}),
            "amount": forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
            "note": forms.Textarea(attrs={"class": "form-control", "rows": 2}),
        }


class ReportFilterForm(forms.Form):
    start_date = forms.DateField(label="من تاريخ", required=False,
                                 widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
    end_date = forms.DateField(label="إلى تاريخ", required=False,
                               widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}))
