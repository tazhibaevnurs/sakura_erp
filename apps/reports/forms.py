from django import forms


class ReportFilterForm(forms.Form):
    date_from = forms.DateField(
        label="С",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    date_to = forms.DateField(
        label="По",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )


class ExportReportForm(forms.Form):
    date_from = forms.DateField(
        label="С",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
    date_to = forms.DateField(
        label="По",
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
    )
